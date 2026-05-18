from fastapi import APIRouter, HTTPException, Query

from app.db import acquire
from app.models import AmenityCategory, NearbyPOI, NearbyResponse

router = APIRouter()

_ALLOWED_AMENITIES: set[str] = set(AmenityCategory.__args__)  # type: ignore[attr-defined]


@router.get("/listings/{listing_id}/nearby", response_model=NearbyResponse)
async def nearby(
    listing_id: int,
    types: str = Query(
        "",
        description="Comma-separated amenity types, e.g. 'subway,grocery'.",
    ),
    radius_m: int = Query(1500, ge=50, le=10_000),
    per_type: int = Query(4, ge=1, le=10),
) -> NearbyResponse:
    """Return the nearest POIs to a listing, filtered by amenity types.

    Limits to `per_type` closest POIs per amenity category to keep the map tidy.
    """
    requested = [t.strip() for t in types.split(",") if t.strip()]
    filtered = [t for t in requested if t in _ALLOWED_AMENITIES]
    if not filtered:
        return NearbyResponse(listing_id=listing_id, pois=[])

    sql = """
        WITH listing AS (
            SELECT location FROM listings WHERE id = $1
        ),
        ranked AS (
            SELECT
                p.id,
                p.poi_type,
                p.name,
                ST_Y(p.location)::float AS lat,
                ST_X(p.location)::float AS lng,
                ST_Distance(p.location::geography, l.location::geography)::int AS distance_m,
                ROW_NUMBER() OVER (
                    PARTITION BY p.poi_type
                    ORDER BY p.location::geography <-> l.location::geography
                ) AS rn
            FROM pois p, listing l
            WHERE p.poi_type = ANY($2::text[])
              AND ST_DWithin(p.location::geography, l.location::geography, $3)
        )
        SELECT id, poi_type, name, lat, lng, distance_m
          FROM ranked
         WHERE rn <= $4
         ORDER BY poi_type, distance_m
    """

    async with acquire() as conn:
        # Verify the listing exists so callers get a 404 instead of an empty body
        exists = await conn.fetchval("SELECT 1 FROM listings WHERE id = $1", listing_id)
        if not exists:
            raise HTTPException(status_code=404, detail="listing not found")
        rows = await conn.fetch(sql, listing_id, filtered, radius_m, per_type)

    return NearbyResponse(
        listing_id=listing_id,
        pois=[
            NearbyPOI(
                id=r["id"],
                poi_type=r["poi_type"],
                name=r["name"],
                lat=r["lat"],
                lng=r["lng"],
                distance_m=r["distance_m"],
            )
            for r in rows
        ],
    )
