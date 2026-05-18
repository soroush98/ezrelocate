"""Claude wrappers: rental-query parsing + recommendation generation.

Both prompts are amenity-aware (OSM-backed). The parser maps phrases like
"walkable to a subway" → `near_amenities: ["subway"]`. The generator receives
each listing's actual nearest-amenity distances in metres, so it can cite real
numbers ("320m from St. Clair West Station") instead of guessing.
"""

import json

from anthropic import AsyncAnthropic

from app.config import get_settings
from app.models import ListingOut, ParsedQuery

_client: AsyncAnthropic | None = None


def _client_singleton() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


PARSER_SYSTEM = """You convert a user's free-text Canadian rental search into a JSON object \
of structured filters. Return ONLY the JSON — no prose, no code fences.

Schema:
{
  "city": "Toronto" | null,                     // Canadian city name or null for any
  "province": "ON" | null,                      // 2-letter province code or null
  "max_rent": 2500 | null,                      // integer CAD/month or null
  "min_rent": null,
  "min_bedrooms": 2 | null,                     // 0.5 means studio/bachelor
  "max_bedrooms": null,
  "min_bathrooms": null,
  "property_types": ["apartment","condo","house","townhouse","basement","room"],
  "furnished": true | false | null,
  "pet_friendly": true | false | null,
  "utilities_required": ["heat","hydro","water","internet","cable"],
  "lease_length_months_max": 6 | null,
  "available_by": "2026-06-01" | null,
  "near_amenities": ["subway","grocery"],       // see allowed list below
  "amenity_max_m": 800,                          // metres; default 800 (~10 min walk)
  "lifestyle_query": "...",                     // free-text vibe phrase
  "commute_target": "University of Alberta" | null,  // SPECIFIC named place (see below)
  "commute_max_km": 10 | null
}

Allowed near_amenities values (use EXACTLY these strings, case-sensitive):
  subway, lrt, train, bus_stop, grocery, cafe, pharmacy,
  park, school, university, library, gym, hospital

Rules:
- Map natural phrases to amenities. Examples:
    "walkable to a subway" / "near TTC" / "by the SkyTrain"      → subway
    "near the C-Train" / "by a streetcar" / "tram"               → lrt
    "near a GO station"                                           → train
    "close to a bus stop"                                         → bus_stop
    "near a grocery store" / "by a Loblaws"                       → grocery
    "near cafes" / "lots of coffee shops"                         → cafe
    "near a park" / "next to a playground"                        → park
    "good for families" (with kids mentioned)                     → school
    "near any university" (generic, no name)                      → university
    "walk to the library"                                         → library
    "near a gym"                                                  → gym
    "near a hospital"                                             → hospital
- **Named landmarks**: if the user names a SPECIFIC place — a particular
  university, transit station, employer, mall, airport, park — set
  `commute_target` to the full name AND set `commute_max_km` from any
  walking/distance hint. Do NOT also add the generic amenity. Examples:
    "near University of Alberta"          → commute_target="University of Alberta", commute_max_km=1.5
    "walkable to McGill"                  → commute_target="McGill University", commute_max_km=1
    "close to Union Station"              → commute_target="Union Station", commute_max_km=1
    "near Pearson Airport"                → commute_target="Toronto Pearson International Airport"
    "near Stanley Park"                   → commute_target="Stanley Park", commute_max_km=1
    "near Eaton Centre"                   → commute_target="Eaton Centre", commute_max_km=1
    "commute to downtown Toronto"         → commute_target="downtown Toronto", commute_max_km=10
  Expand common abbreviations: "U of A" → "University of Alberta", "U of T" → "University of Toronto", "UBC" → "University of British Columbia", "SFU" → "Simon Fraser University", "McGill" → "McGill University".
- `commute_max_km` defaults: "walkable / walk to" → 1, "near" without distance → 2, "commute to" → 10. Use the user's number if stated.
- Multiple amenities allowed: ["subway","grocery","park"]
- amenity_max_m: extract if the user gave a number ("within 500m", "5 min walk"
  ≈ 400m, "10 min walk" ≈ 800m). Default 800 if unspecified.
- Pull every vibe / walkability / neighbourhood feel phrase into lifestyle_query.
- Infer min_bedrooms from family/roommate mentions ("with my partner" => 1,
  "2 kids" => min 2 or 3). "Studio"/"bachelor" => min_bedrooms=0.5.
- Normalise Canadian province names to 2-letter code.
- Never fabricate numbers the user didn't imply."""


async def parse_query(user_query: str) -> ParsedQuery:
    settings = get_settings()
    msg = await _client_singleton().messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=PARSER_SYSTEM,
        messages=[{"role": "user", "content": user_query}],
    )
    raw = "".join(block.text for block in msg.content if block.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    data = json.loads(raw)
    return ParsedQuery(**data)


GENERATOR_SYSTEM = """You are a Canadian rental-search advisor. Given the user's original \
prompt and a ranked list of candidate rental listings, write a concise recommendation that:

- Cites each listing by numeric id, e.g. "Listing 42 in Leslieville".
- When citing transit / amenities, use the REAL `amenity_distances_m` values \
  provided for each listing. Example: "320m from a subway station (≈4 min walk)". \
  NEVER invent numbers. If the user asked about an amenity that isn't in \
  amenity_distances_m for a listing, say so honestly: "No subway within 5km."
- Convert metres to minutes when natural (assume ~80m/min walking pace).
- Explains *why* each top pick fits the user's stated criteria — rent, beds, \
  pets, utilities, lease, plus those concrete amenity distances.
- Notes trade-offs honestly ("smaller, but 5× closer to grocery").
- Frames neighbourhoods as "fits your preferences" — never "good vs bad".
- Flags missing info ("listing doesn't specify pet policy — verify").
- Keeps it under 250 words. No emoji. No headers."""


async def generate_recommendation(
    user_query: str,
    parsed: ParsedQuery,
    listings: list[ListingOut],
) -> str:
    settings = get_settings()
    payload = {
        "user_query": user_query,
        "parsed_filters": parsed.model_dump(mode="json"),
        "candidates": [l.model_dump(mode="json") for l in listings],
    }
    msg = await _client_singleton().messages.create(
        model=settings.anthropic_model,
        max_tokens=900,
        system=GENERATOR_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()
