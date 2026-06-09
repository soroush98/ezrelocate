"""Hybrid retrieval for Canadian rentals — with OSM amenity proximity.

Pipeline:
  1. SQL hard-filter: status, city/province, rent, beds, baths, pets, furnished,
     utilities, lease, availability, and `near_amenities` proximity (OSM-backed).
  2. pgvector cosine rerank on the listing description embedding.
  3. Optional PostGIS commute filter.
"""

import json

from app.db import acquire
from app.models import AmenityCategory, ListingOut, ParsedQuery
from app.services.embeddings import embed_query


def _as_dict(v) -> dict:
    """asyncpg returns JSONB values as raw JSON strings by default."""
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    return json.loads(v)

TOP_K = 5

# Whitelist for amenity filter clauses — prevents SQL injection via Claude.
_ALLOWED_AMENITIES: set[str] = set(AmenityCategory.__args__)  # type: ignore[attr-defined]


async def retrieve(parsed: ParsedQuery) -> list[ListingOut]:
    intent_embed = (
        await embed_query(parsed.lifestyle_query) if parsed.lifestyle_query.strip() else None
    )

    commute_point_wkt: str | None = None
    if parsed.commute_target:
        commute_point_wkt = await _geocode_commute_target(
            parsed.commute_target, parsed.city, parsed.province
        )

    sql, args = _build_candidate_sql(parsed, intent_embed, commute_point_wkt)

    async with acquire() as conn:
        rows = await conn.fetch(sql, *args)

    return [
        ListingOut(
            id=row["id"],
            source=row["source"],
            url=row["url"],
            title=row["title"],
            address=row["address"],
            city=row["city"],
            province=row["province"],
            lat=row["lat"],
            lng=row["lng"],
            monthly_rent=row["monthly_rent"],
            bedrooms=float(row["bedrooms"]) if row["bedrooms"] is not None else None,
            bathrooms=float(row["bathrooms"]) if row["bathrooms"] is not None else None,
            sqft=row["sqft"],
            property_type=row["property_type"],
            furnished=row["furnished"],
            pet_friendly=row["pet_friendly"],
            utilities_included=list(row["utilities_included"] or []),
            lease_length_months=row["lease_length_months"],
            available_from=row["available_from"],
            amenity_distances_m=_as_dict(row["amenity_distances_m"]),
            description=row["description"],
            score=float(row["score"]),
        )
        for row in rows
    ]


def _build_candidate_sql(
    parsed: ParsedQuery,
    intent_embed: list[float] | None,
    commute_point_wkt: str | None,
) -> tuple[str, list]:
    where = ["l.status = 'active'", "l.desc_embed IS NOT NULL"]
    args: list = []

    def add(clause_tpl: str, value) -> None:
        args.append(value)
        where.append(clause_tpl.format(p=f"${len(args)}"))

    if parsed.city:
        add("l.city ILIKE '%' || {p} || '%'", parsed.city)
    if parsed.province:
        add("l.province = {p}", parsed.province.upper())
    if parsed.max_rent is not None:
        add("l.monthly_rent <= {p}", parsed.max_rent)
    if parsed.min_rent is not None:
        add("l.monthly_rent >= {p}", parsed.min_rent)
    if parsed.min_bedrooms is not None:
        add("l.bedrooms >= {p}", parsed.min_bedrooms)
    if parsed.max_bedrooms is not None:
        add("l.bedrooms <= {p}", parsed.max_bedrooms)
    if parsed.min_bathrooms is not None:
        add("l.bathrooms >= {p}", parsed.min_bathrooms)
    if parsed.property_types:
        add("l.property_type = ANY({p})", parsed.property_types)
    if parsed.furnished is not None:
        add("l.furnished = {p}", parsed.furnished)
    if parsed.pet_friendly is not None:
        add("l.pet_friendly = {p}", parsed.pet_friendly)
    if parsed.utilities_required:
        add("l.utilities_included @> {p}", parsed.utilities_required)
    if parsed.lease_length_months_max is not None:
        add(
            "(l.lease_length_months IS NULL OR l.lease_length_months <= {p})",
            parsed.lease_length_months_max,
        )
    if parsed.available_by is not None:
        add("(l.available_from IS NULL OR l.available_from <= {p})", parsed.available_by)

    # Amenity proximity (OSM-backed). Each requested amenity must be within
    # parsed.amenity_max_m metres of the listing. Capped at 5km so a confused
    # LLM widening the filter to "anywhere in the city" can't silently drop it.
    max_m = max(50, min(int(parsed.amenity_max_m or 800), 5000))
    for amenity in parsed.near_amenities:
        if amenity not in _ALLOWED_AMENITIES:
            continue
        # Whitelisted, so safe to interpolate the key.
        where.append(
            f"(l.amenity_distances_m ? '{amenity}' "
            f"AND (l.amenity_distances_m->>'{amenity}')::int <= {max_m})"
        )

    # Lifestyle rerank. pgvector cosine *distance* is in [0, 2]; similarity =
    # 1 - distance, against the listing's own description embedding.
    if intent_embed is not None:
        embed_str = "[" + ",".join(f"{x:.6f}" for x in intent_embed) + "]"
        args.append(embed_str)
        listing_p = f"${len(args)}"
        score_expr = f"(1 - (l.desc_embed <=> {listing_p}::vector))"
    else:
        score_expr = "0.0"

    if commute_point_wkt is not None:
        args.append(commute_point_wkt)
        commute_p = f"${len(args)}"
        if parsed.commute_max_km is not None:
            args.append(parsed.commute_max_km * 1000)
            radius_p = f"${len(args)}"
            where.append(
                f"(l.location IS NULL OR ST_DWithin(l.location::geography, "
                f"ST_GeogFromText({commute_p}), {radius_p}))"
            )

    sql = f"""
        SELECT
            l.id,
            l.source,
            l.url,
            l.title,
            l.address,
            l.city,
            l.province,
            l.monthly_rent,
            l.bedrooms,
            l.bathrooms,
            l.sqft,
            l.property_type,
            l.furnished,
            l.pet_friendly,
            l.utilities_included,
            l.lease_length_months,
            l.available_from,
            l.amenity_distances_m,
            l.description,
            CASE WHEN l.location IS NULL THEN NULL ELSE ST_Y(l.location) END AS lat,
            CASE WHEN l.location IS NULL THEN NULL ELSE ST_X(l.location) END AS lng,
            ({score_expr}) AS score
        FROM listings l
        WHERE {' AND '.join(where)}
        ORDER BY score DESC NULLS LAST, l.last_seen_at DESC, l.id
        LIMIT {TOP_K}
    """
    return sql, args


async def _geocode_commute_target(
    target: str, city: str | None, province: str | None
) -> str | None:
    """Resolve a named place to a WKT POINT.

    Matches against POIs by name — covers specific universities, transit
    stations, parks, airports, malls, anything we ingested from OSM with a
    `name` tag. Ranked by pg_trgm similarity so 'McGill' matches
    'McGill University'.
    """
    async with acquire() as conn:
        # 1) POI name match — restrict to a city when supplied so 'Stanley Park'
        # in Vancouver isn't matched to a Stanley Park elsewhere. OSM POIs don't
        # carry city tags reliably, so we bound via the centroid of that city's
        # active listings and a 60km radius (covers metro areas like GTA).
        poi_row = await conn.fetchrow(
            """
            WITH city_pt AS (
                SELECT ST_Centroid(ST_Collect(location))::geography AS pt
                FROM listings
                WHERE location IS NOT NULL
                  AND status = 'active'
                  AND ($2::text IS NULL OR LOWER(city) = LOWER($2))
                  AND ($3::text IS NULL OR province = UPPER($3))
            )
            SELECT ST_AsText(p.location) AS wkt, p.name, p.poi_type
            FROM pois p
            WHERE p.name IS NOT NULL
              AND p.name % $1   -- pg_trgm similarity above default 0.3 threshold
              AND (
                $2::text IS NULL
                OR (SELECT pt FROM city_pt) IS NULL
                OR ST_DWithin(p.location::geography, (SELECT pt FROM city_pt), 60000)
              )
            ORDER BY similarity(p.name, $1) DESC, length(p.name) ASC
            LIMIT 1
            """,
            target,
            city,
            province,
        )
    return poi_row["wkt"] if poi_row else None
