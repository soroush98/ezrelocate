"""Per-listing nearest-amenity distances.

For each active listing, scan POIs within a 5km radius and store the minimum
distance to each poi_type in `listings.amenity_distances_m` (JSONB).

Designed to be re-run after every refresh (cheap thanks to the GIST index).

Run:
    cd backend && python -m etl.compute_amenity_distances
"""

import asyncio
import time

from etl._common import connect

RADIUS_M = 5000  # match the radius implied by amenity_distances_m semantics


SQL_UPDATE = f"""
WITH nearest AS (
    SELECT
        l.id AS listing_id,
        p.poi_type,
        MIN(ST_Distance(p.location::geography, l.location::geography))::int AS m
    FROM listings l
    JOIN pois p
      ON ST_DWithin(p.location::geography, l.location::geography, {RADIUS_M})
    WHERE l.status = 'active'
      AND l.location IS NOT NULL
    GROUP BY l.id, p.poi_type
),
rolled AS (
    SELECT listing_id, jsonb_object_agg(poi_type, m) AS amenities
    FROM nearest
    GROUP BY listing_id
)
UPDATE listings l
   SET amenity_distances_m = COALESCE(r.amenities, '{{}}'::jsonb)
  FROM rolled r
 WHERE r.listing_id = l.id
RETURNING l.id;
"""


async def main() -> None:
    t0 = time.time()
    async with connect() as conn:
        # Sanity check
        poi_count = await conn.fetchval("SELECT COUNT(*) FROM pois")
        active_listings = await conn.fetchval(
            "SELECT COUNT(*) FROM listings WHERE status='active' AND location IS NOT NULL"
        )
        if poi_count == 0:
            print("no POIs in the DB yet — run etl/load_osm_pois first")
            return
        print(f"computing distances · {active_listings} active listings · {poi_count} POIs")

        # Reset to empty so removed POI categories don't linger.
        await conn.execute(
            "UPDATE listings SET amenity_distances_m = '{}'::jsonb "
            "WHERE status='active' AND amenity_distances_m <> '{}'::jsonb"
        )

        rows = await conn.fetch(SQL_UPDATE)

    print(f"updated {len(rows)} listings in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
