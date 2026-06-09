"""Ingest OSM POIs from Geofabrik province extracts — offline, no Overpass.

Why this exists: the public Overpass API rate-limits CI IPs hard (429s) and
times out, which repeatedly broke the nightly run. POIs are static
infrastructure, so we don't need a live API: download each province's
`.osm.pbf` from Geofabrik once, stream-extract the POIs we care about with
pyosmium, and upsert into `pois`. Reliable and rate-limit free.

Classification reuses etl.load_osm_pois.classify(), so POIs land with the exact
same poi_type and `osm:<type>:<id>` source_id as the old Overpass path — re-runs
just upsert, no duplicates.

Run:
    cd backend && python -m etl.load_osm_pois_geofabrik              # all provinces with listings
    cd backend && python -m etl.load_osm_pois_geofabrik --province ON
    cd backend && python -m etl.load_osm_pois_geofabrik --pbf /path/to.osm.pbf --province ON
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile

import httpx
import osmium

from etl._common import connect
from etl.load_osm_pois import classify

# Province code → Geofabrik Canada sub-extract slug.
PROVINCE_SLUGS: dict[str, str] = {
    "ON": "ontario",
    "QC": "quebec",
    "BC": "british-columbia",
    "AB": "alberta",
    "MB": "manitoba",
    "SK": "saskatchewan",
    "NS": "nova-scotia",
    "NB": "new-brunswick",
    "NL": "newfoundland-and-labrador",
    "PE": "prince-edward-island",
    "NT": "northwest-territories",
    "YT": "yukon",
    "NU": "nunavut",
}
GEOFABRIK_URL = "https://download.geofabrik.de/north-america/canada/{slug}-latest.osm.pbf"

# Disk-backed node-location index so a big province (ON/QC) can't blow the CI
# runner's RAM while we resolve way geometries.
_INDEX_TYPE = "sparse_file_array"


class _POIHandler(osmium.SimpleHandler):
    """Collect POIs from nodes and ways, classified by our category rules.

    Ways (parks, schools, hospitals mapped as polygons) get a centroid averaged
    from their node coordinates — exact enough for amenity-proximity scoring,
    where the radius is kilometres. Relations are skipped: almost all POIs we
    care about are nodes or single closed ways.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple] = []
        self._seen: set[str] = set()

    def node(self, n: "osmium.osm.Node") -> None:
        if n.location.valid():
            self._consider(n.tags, n.id, "node", n.location.lat, n.location.lon)

    def way(self, w: "osmium.osm.Way") -> None:
        try:
            pts = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
        except osmium.InvalidLocationError:
            pts = []
        if not pts:
            return
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        self._consider(w.tags, w.id, "way", lat, lon)

    def _consider(self, tags, osm_id: int, osm_type: str, lat: float, lon: float) -> None:
        td = {t.k: t.v for t in tags}
        poi_type = classify(td)
        if not poi_type:
            return
        source_id = f"osm:{osm_type}:{osm_id}"
        if source_id in self._seen:
            return
        self._seen.add(source_id)
        name = td.get("name") or td.get("name:en")
        self.rows.append(("osm", source_id, poi_type, name, lon, lat, json.dumps(td)))


def _download_extract(slug: str, dest_dir: str) -> str:
    """Download a province .pbf to dest_dir (skip if already present)."""
    url = GEOFABRIK_URL.format(slug=slug)
    path = os.path.join(dest_dir, f"{slug}.osm.pbf")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"  using cached {path} ({os.path.getsize(path) / 1e6:.0f} MB)")
        return path
    print(f"  downloading {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    print(f"  saved {path} ({os.path.getsize(path) / 1e6:.0f} MB)")
    return path


def extract_pois(pbf_path: str) -> list[tuple]:
    """Parse a .pbf and return upsert-ready POI rows."""
    handler = _POIHandler()
    with tempfile.NamedTemporaryFile(suffix=".idx") as idx_file:
        handler.apply_file(
            pbf_path, locations=True, idx=f"{_INDEX_TYPE},{idx_file.name}"
        )
    return handler.rows


async def upsert_pois(conn, rows: list[tuple], chunk: int = 2000) -> tuple[int, int]:
    """Chunked unnest upsert into `pois`. Returns (inserted, updated)."""
    inserted = updated = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start:start + chunk]
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
    return inserted, updated


async def _provinces_with_listings() -> list[str]:
    async with connect() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT province FROM listings "
            "WHERE status = 'active' AND province IS NOT NULL"
        )
    return [r["province"] for r in rows]


async def main(only_province: str | None, pbf_override: str | None) -> None:
    if only_province:
        provinces = [only_province.upper()]
    else:
        provinces = await _provinces_with_listings()
    provinces = [p for p in provinces if p in PROVINCE_SLUGS]
    if not provinces:
        print("no provinces to ingest", file=sys.stderr)
        sys.exit(1)

    print(f"=== Geofabrik POI ingest · {len(provinces)} province(s): "
          f"{', '.join(sorted(provinces))} ===")

    failed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="geofabrik-") as work:
        for prov in provinces:
            slug = PROVINCE_SLUGS[prov]
            print(f"\n--- {prov} ({slug}) ---")
            try:
                pbf = pbf_override or _download_extract(slug, work)
                rows = extract_pois(pbf)
                print(f"  extracted {len(rows)} POIs")
                if rows:
                    async with connect() as conn:
                        ins, upd = await upsert_pois(conn, rows)
                    print(f"  upsert: +{ins} new · {upd} refreshed")
            except Exception as e:
                print(f"  !! {prov} failed: {type(e).__name__}: {e}", file=sys.stderr)
                failed.append(prov)

    if failed:
        print(f"\n!! {len(failed)} province(s) failed: {', '.join(failed)}",
              file=sys.stderr)
        sys.exit(1)
    print("\n=== done ===")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--province", help="ingest a single province by code, e.g. ON")
    p.add_argument("--pbf", help="use a local .pbf instead of downloading "
                                 "(requires --province)")
    args = p.parse_args()
    asyncio.run(main(args.province, args.pbf))
