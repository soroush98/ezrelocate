"""Ingest OpenStreetMap POIs via the Overpass API.

For each city we already have listings in, derive a bounding box from those
listings' lat/lng, expand it by ~5km, then ask Overpass for every POI of the
13 categories below within that box. Idempotent — re-running just upserts.

Categories: subway, lrt, train, bus_stop, grocery, cafe, pharmacy, park,
school, university, library, gym, hospital.

Volume: ~150-250k POIs total for the 22 cities.

Run:
    cd backend && python -m etl.load_osm_pois
    cd backend && python -m etl.load_osm_pois --dry-run        # just print counts
    cd backend && python -m etl.load_osm_pois --city Toronto   # one city only
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from etl._common import connect

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# (poi_type, list-of-Overpass-filter-stanzas).
# Each stanza is appended to node/way/relation queries inside the bounding box.
# The first matching category wins when one POI has multiple tags.
CATEGORIES: list[tuple[str, list[str]]] = [
    ("subway",     ['["railway"="subway_entrance"]',
                    '["public_transport"="station"]["subway"="yes"]',
                    '["station"="subway"]']),
    ("lrt",        ['["railway"="tram_stop"]',
                    '["railway"="light_rail"]',
                    '["station"="light_rail"]']),
    ("train",      ['["railway"="station"]["station"!="subway"]["station"!="light_rail"]',
                    '["railway"="halt"]']),
    ("bus_stop",   ['["highway"="bus_stop"]']),
    ("grocery",    ['["shop"="supermarket"]',
                    '["shop"="convenience"]']),
    ("cafe",       ['["amenity"="cafe"]',
                    '["shop"="coffee"]']),
    ("pharmacy",   ['["amenity"="pharmacy"]']),
    ("park",       ['["leisure"="park"]',
                    '["leisure"="playground"]']),
    ("school",     ['["amenity"="school"]',
                    '["amenity"="kindergarten"]',
                    '["amenity"="childcare"]']),
    ("university", ['["amenity"="university"]',
                    '["amenity"="college"]']),
    ("library",    ['["amenity"="library"]']),
    ("gym",        ['["leisure"="fitness_centre"]',
                    '["leisure"="sports_centre"]']),
    ("hospital",   ['["amenity"="hospital"]',
                    '["amenity"="clinic"]']),
]

# Each category's Overpass tag-spec (in matching priority order) → poi_type.
# Used at classify-time to pick the best label for an element that matched
# multiple categories' filters.
_CATEGORY_PRIORITY = [t for t, _ in CATEGORIES]

BBOX_BUFFER_DEG = 0.05  # ≈ 5.5km — generous around each city's listing footprint
TIMEOUT_SECONDS = 90    # Overpass needs room for big bboxes


async def fetch_city_bboxes(only_city: str | None) -> list[dict]:
    """Compute bounding boxes from existing active listings, one row per city.

    Order: highest listing-count first so demoable cities (Toronto / Montreal /
    Vancouver / Calgary / Edmonton) finish before the long tail of small towns.
    """
    sql = """
        SELECT
            city,
            province,
            ST_YMin(ST_Extent(location)::geometry) - $1::float8 AS south,
            ST_XMin(ST_Extent(location)::geometry) - $1::float8 AS west,
            ST_YMax(ST_Extent(location)::geometry) + $1::float8 AS north,
            ST_XMax(ST_Extent(location)::geometry) + $1::float8 AS east,
            COUNT(*)::int AS listing_count
        FROM listings
        WHERE status = 'active' AND location IS NOT NULL
        GROUP BY city, province
        ORDER BY listing_count DESC
    """
    async with connect() as conn:
        rows = await conn.fetch(sql, BBOX_BUFFER_DEG)
    cities = [dict(r) for r in rows]
    if only_city:
        cities = [c for c in cities if only_city.lower() in c["city"].lower()]
    return cities


def build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """One single Overpass query covering every category, returned as JSON."""
    south, west, north, east = bbox
    box = f"({south:.4f},{west:.4f},{north:.4f},{east:.4f})"

    parts: list[str] = []
    for _poi_type, filters in CATEGORIES:
        for f in filters:
            for kind in ("node", "way", "relation"):
                parts.append(f"  {kind}{f}{box};")
    body = "\n".join(parts)

    return f"""[out:json][timeout:{TIMEOUT_SECONDS}];
(
{body}
);
out center tags;
"""


def classify(tags: dict[str, str]) -> str | None:
    """Map an OSM element's tags → our internal poi_type.

    Each category's stanzas are checked in declaration order. Returns the
    first match, so e.g. a subway entrance never gets labelled bus_stop.
    """
    for poi_type, stanzas in CATEGORIES:
        for stanza in stanzas:
            if _stanza_matches(stanza, tags):
                return poi_type
    return None


def _stanza_matches(stanza: str, tags: dict[str, str]) -> bool:
    """Parse an Overpass filter like '["amenity"="cafe"]' and check tags.

    Supports k="v" equality and k!="v" inequality (no regex, no fancy stuff).
    """
    # Strip outer brackets, split on `][`, parse each pair
    body = stanza.strip("[]")
    pairs = body.split("][")
    for raw in pairs:
        if "!=" in raw:
            k, v = raw.split("!=", 1)
            if tags.get(k.strip('"')) == v.strip('"'):
                return False
        elif "=" in raw:
            k, v = raw.split("=", 1)
            if tags.get(k.strip('"')) != v.strip('"'):
                return False
        else:
            # tag-presence only, e.g. ["wheelchair"]
            if raw.strip('"') not in tags:
                return False
    return True


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=8, max=120))
async def overpass_query(
    client: httpx.AsyncClient, query: str, endpoint_idx: int = 0
) -> list[dict]:
    """POST a query to Overpass, falling through mirrors on hard failures."""
    try:
        r = await client.post(
            OVERPASS_ENDPOINTS[endpoint_idx],
            data={"data": query},
            timeout=TIMEOUT_SECONDS + 10,
        )
        if r.status_code == 429 or r.status_code >= 500:
            r.raise_for_status()
        r.raise_for_status()
        return r.json().get("elements", [])
    except Exception:
        # Try next mirror once before propagating to tenacity's retry.
        if endpoint_idx + 1 < len(OVERPASS_ENDPOINTS):
            return await overpass_query(client, query, endpoint_idx + 1)
        raise


def element_latlng(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center")
    if center and "lat" in center and "lon" in center:
        return center["lat"], center["lon"]
    return None


async def ingest_city(client: httpx.AsyncClient, city: dict, dry_run: bool) -> dict:
    bbox = (city["south"], city["west"], city["north"], city["east"])
    print(f"\n--- {city['city']}, {city['province']}  "
          f"(bbox {bbox[0]:.3f},{bbox[1]:.3f},{bbox[2]:.3f},{bbox[3]:.3f}) ---")

    query = build_overpass_query(bbox)
    elements = await overpass_query(client, query)

    rows: list[tuple] = []
    type_counts: Counter[str] = Counter()
    skipped_unclassified = 0

    for el in elements:
        tags = el.get("tags") or {}
        poi_type = classify(tags)
        if not poi_type:
            skipped_unclassified += 1
            continue
        latlng = element_latlng(el)
        if not latlng:
            continue
        lat, lng = latlng
        source_id = f"osm:{el['type']}:{el['id']}"
        name = tags.get("name") or tags.get("name:en")
        rows.append((
            "osm",
            source_id,
            poi_type,
            name,
            lng, lat,
            json.dumps(tags),
        ))
        type_counts[poi_type] += 1

    print(f"  fetched {len(elements)} OSM elements · classified {len(rows)} · "
          f"skipped {skipped_unclassified} unclassified")
    for t in _CATEGORY_PRIORITY:
        if type_counts.get(t):
            print(f"    {t:11s} {type_counts[t]:>6d}")

    if dry_run or not rows:
        return {"city": city["city"], "kept": len(rows)}

    # Batched upsert: one round-trip per chunk via unnest. The old per-row
    # loop was ~200ms × N round-trips, which for big cities (~30k rows) takes
    # ~90 min/city against a remote DB. Chunked unnest brings it to seconds.
    inserted = updated = 0
    CHUNK = 2000
    async with connect() as conn:
        for start in range(0, len(rows), CHUNK):
            batch = rows[start:start + CHUNK]
            result = await conn.fetch(
                """
                INSERT INTO pois (source, source_id, poi_type, name, location, attrs)
                SELECT source, source_id, poi_type, name,
                       ST_SetSRID(ST_MakePoint(lng, lat), 4326),
                       attrs::jsonb
                FROM unnest($1::text[], $2::text[], $3::text[], $4::text[],
                            $5::float8[], $6::float8[], $7::text[])
                  AS t(source, source_id, poi_type, name, lng, lat, attrs)
                ON CONFLICT (source, source_id) DO UPDATE SET
                  poi_type   = EXCLUDED.poi_type,
                  name       = EXCLUDED.name,
                  location   = EXCLUDED.location,
                  attrs      = EXCLUDED.attrs,
                  updated_at = NOW()
                RETURNING (xmax = 0) AS inserted
                """,
                [r[0] for r in batch],
                [r[1] for r in batch],
                [r[2] for r in batch],
                [r[3] for r in batch],
                [r[4] for r in batch],
                [r[5] for r in batch],
                [r[6] for r in batch],
            )
            for row in result:
                if row["inserted"]:
                    inserted += 1
                else:
                    updated += 1
    print(f"  upsert: +{inserted} new · {updated} refreshed")
    return {"city": city["city"], "kept": len(rows),
            "inserted": inserted, "updated": updated}


async def main(only_city: str | None, dry_run: bool) -> None:
    cities = await fetch_city_bboxes(only_city)
    if not cities:
        print("no cities found — load some listings first", file=sys.stderr)
        sys.exit(1)

    print(f"=== OSM POI ingest · {len(cities)} cities ===")
    print(f"categories: {', '.join(t for t, _ in CATEGORIES)}")

    async with httpx.AsyncClient(
        headers={"User-Agent": "EZrelocate-OSM-ingest (esmailian98@gmail.com)"},
    ) as client:
        results = []
        for i, city in enumerate(cities, 1):
            try:
                r = await ingest_city(client, city, dry_run)
                results.append(r)
            except Exception as e:
                print(f"  !! {city['city']} failed: {type(e).__name__}: {e}")
            # Be nice — Overpass instances are donated infra.
            if i < len(cities):
                await asyncio.sleep(3)

    total_kept = sum(r.get("kept", 0) for r in results)
    print(f"\n=== done · {total_kept} POIs across {len(results)} cities ===")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--city", help="ingest a single city by name (substring match)")
    p.add_argument("--dry-run", action="store_true",
                   help="hit Overpass but skip the DB upsert")
    args = p.parse_args()
    asyncio.run(main(args.city, args.dry_run))
