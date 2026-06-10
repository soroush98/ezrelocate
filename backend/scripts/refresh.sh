#!/usr/bin/env bash
# EZrelocate — nightly refresh.
# Re-scrapes Kijiji (round-robin across cities), recomputes per-listing amenity
# distances, then embeds new listings, and marks stale rows.
#
# OSM POIs are static infrastructure and load on a separate weekly schedule
# (.github/workflows/osm-pois.yml → etl.load_osm_pois_geofabrik), so they're
# intentionally NOT refreshed here.
#
# Designed to be cron / launchd / GitHub Actions friendly:
#   - Resolves its own location, doesn't depend on caller's CWD
#   - Activates the project venv explicitly
#   - Loads .env so DATABASE_URL etc. are available
#   - All output goes to stdout/stderr; caller decides where to log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$BACKEND_DIR")"
cd "$BACKEND_DIR"

# 1. Project venv
if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "ERROR: backend/.venv not found. Run 'uv venv && uv pip install -e .' first." >&2
    exit 1
fi

# 2. .env (DATABASE_URL, ANTHROPIC_API_KEY, VOYAGE_API_KEY)
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

# 3. Scrape + amenities + embed
echo "=== $(date -Iseconds) EZrelocate refresh starting ==="

echo "--- Kijiji round-robin (100 per city) ---"
python -u -m etl.scrape_kijiji --per-city 100

echo "--- Recomputing per-listing amenity distances ---"
python -u -m etl.compute_amenity_distances

echo "--- Embedding new listings ---"
python -u -m etl.embed_all

echo "=== $(date -Iseconds) refresh complete ==="
