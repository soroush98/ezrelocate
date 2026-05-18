# EZrelocate

Canada-wide rental search. You describe what you're looking for in plain English;
the system returns real rental listings on a map, with reasoning that cites each
pick by id.

The interesting part isn't the chat — it's the hybrid retrieval pipeline running
over a continuously-refreshed national rental index:

> **Kijiji scraper (national, per-city round-robin) → Postgres + PostGIS + pgvector
> → SQL hard-filter on rent/beds/pets/utilities → pgvector cosine rerank on a 60/40
> blend of neighbourhood-profile-fit and listing-description-fit → optional PostGIS
> commute filter → Claude generates the final recommendation citing specific
> listing ids.**

## Stack

| Layer | Choice |
|---|---|
| DB | Postgres 17 + PostGIS 3 + pgvector |
| Backend | FastAPI 0.136 (Python 3.12), asyncpg |
| LLM | Anthropic SDK 0.102 — Claude for query parsing + recommendation generation |
| Embeddings | Voyage AI `voyage-3-large` (1024-dim) |
| Frontend | Next.js 16.2 + React 19 + Tailwind v4 + MapLibre GL 5 (Carto Voyager basemap) |
| Scraper | httpx + selectolax, polite rate-limited, per-city round-robin |

## Data sources

| Source | Coverage | Why |
|---|---|---|
| **Kijiji** | National apartments + houses for rent (~54k inventory) | High volume, plain-HTTP scrapable, structured data in Apollo cache (`__NEXT_DATA__` → `__APOLLO_STATE__.RealEstateListing:<id>`) |

**Tried and rejected:**
- **rentals.ca** — Cloudflare bot challenge (HTTP 403 + JS-required Turnstile).
  Needs Playwright or a paid proxy; not portfolio-polite.
- **Realtor.ca / CREA DDF** — Cloudflare-blocked, ToS-prohibited, requires licensed
  brokerage sponsorship.
- **Facebook Marketplace** — auth wall + heavy anti-bot + ToS. Most FB rentals are
  duplicated to Kijiji anyway.

Scraping is **batch, not per-query.** `backend/scripts/refresh.sh` runs on a
schedule (nightly at 1 AM via launchd, see below); user queries hit the warm
pgvector / PostGIS index. Listings not re-seen in 72h auto-flip to
`status='stale'` and stop appearing in results.

## Repository layout

```
.
├── infra/
│   ├── Dockerfile                       # postgres:17-bookworm + postgis + pgvector
│   ├── docker-compose.yml
│   ├── init/01-extensions.sql           # CREATE EXTENSION postgis, vector, pg_trgm
│   └── com.ezrelocate.refresh.plist     # launchd job — nightly 1 AM refresh
├── db/
│   └── schema.sql                       # listings, neighborhoods (+ HNSW & GIST indexes)
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                      # FastAPI app + lifespan
│   │   ├── config.py                    # pydantic-settings
│   │   ├── db.py                        # asyncpg pool
│   │   ├── models.py                    # Pydantic request/response types
│   │   ├── routes/query.py              # POST /api/query
│   │   └── services/
│   │       ├── embeddings.py            # Voyage AI wrapper
│   │       ├── llm.py                   # Claude parse + generate
│   │       └── retrieval.py             # Hybrid SQL + pgvector + PostGIS
│   ├── etl/
│   │   ├── _scrape.py                   # PoliteClient, ScrapedListing, upsert, mark_stale
│   │   ├── scrape_kijiji.py             # National per-city round-robin scraper
│   │   └── embed_all.py                 # Voyage backfill for active listings
│   └── scripts/
│       ├── init_db.sh                   # Apply db/schema.sql
│       └── refresh.sh                   # cron/launchd entrypoint
├── frontend/                            # Next.js 16 · Tailwind v4 · MapLibre · Geist
│   └── src/
│       ├── app/{layout,page}.tsx
│       ├── components/{Map,QueryPanel,ListingCard,FilterChips,Pill,Icon}.tsx
│       └── lib/types.ts
└── .env.example
```

## Run it locally

### 0. Prereqs

- Docker
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (or any pip/venv tool)
- Node 22+ (npm or pnpm)
- Anthropic API key, Voyage AI API key (Voyage requires payment-method-on-file
  for usable rate limits; you still get 200M free tokens)

### 1. Bring up the database

```bash
cp .env.example .env       # fill in keys
cd infra && docker compose up -d --build
cd ..
./backend/scripts/init_db.sh   # applies db/schema.sql
```

### 2. Install the backend

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e .
```

### 3. First crawl (~30–60 min for ~4,400 balanced listings)

```bash
# Dry-run first — confirms the parser still matches Kijiji's __NEXT_DATA__ shape.
python -m etl.scrape_kijiji --per-city 2 --dry-run

# Real crawl — round-robin across 22 cities, ~250 each.
python -m etl.scrape_kijiji --per-city 250

# Embed everything (needs VOYAGE_API_KEY in .env).
python -m etl.embed_all
```

### 4. Start the API

```bash
uvicorn app.main:app --reload
# http://localhost:8000/health
# http://localhost:8000/docs
```

### 5. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
# http://localhost:3000
```

### 6. Schedule the nightly 1 AM refresh

**Option A — launchd (recommended on macOS):**

```bash
cp infra/com.ezrelocate.refresh.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ezrelocate.refresh.plist

# Verify it's scheduled:
launchctl print gui/$(id -u)/com.ezrelocate.refresh | head -20

# Trigger one run right now (skip the wait):
launchctl kickstart gui/$(id -u)/com.ezrelocate.refresh

# Tail logs:
tail -f ~/Library/Logs/ezrelocate-refresh.log

# Uninstall:
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ezrelocate.refresh.plist
rm ~/Library/LaunchAgents/com.ezrelocate.refresh.plist
```

**Option B — crontab (Linux servers or macOS):**

```bash
( crontab -l 2>/dev/null; echo "0 1 * * * /Users/soroosh/EZrelocate/backend/scripts/refresh.sh >> $HOME/Library/Logs/ezrelocate-refresh.log 2>&1" ) | crontab -
```

**macOS sleep caveat:** if the laptop is asleep at 1 AM, launchd will fire the
job the next time the machine wakes. For guaranteed wake-up: `sudo pmset repeat
wakeorpoweron MTWRFSU 00:55:00`.

## API

`POST /api/query`

```json
{ "query": "Toronto, $2500/mo, 1 bedroom, pet-friendly, near a subway station" }
```

Response:

```json
{
  "query": "...",
  "parsed": {
    "city": "Toronto",
    "province": "ON",
    "max_rent": 2500,
    "min_bedrooms": 1,
    "pet_friendly": true,
    "lifestyle_query": "near a subway station"
  },
  "listings": [
    {
      "id": 1042,
      "source": "kijiji",
      "url": "https://www.kijiji.ca/v-apartments-condos/.../12345",
      "monthly_rent": 2350,
      "bedrooms": 1, "bathrooms": 1, "sqft": 580,
      "pet_friendly": true,
      "utilities_included": ["heat", "water"],
      "city": "City of Toronto", "province": "ON",
      "neighborhood": null,
      "lat": 43.66, "lng": -79.33,
      "score": 0.78
    }
  ],
  "reasoning": "Listing 1042 in Leslieville fits because..."
}
```

## A note on scraping ethics & ToS

Kijiji's ToS restricts scraping. For a portfolio project crawling at polite rates
(3 concurrent requests, ~1s jitter, ~250 listings per city per refresh) this is
the standard gray area many tools occupy. Don't redistribute the data and don't
run this at commercial scale without negotiated access. If you ever deploy a
public demo, expect to need a residential-proxy provider (BrightData, Apify) to
avoid IP-level rate limits.

## Resume framing

> Built EZrelocate — a Canada-wide rental search system with hybrid retrieval
> combining PostGIS spatial queries, pgvector semantic search, and Claude for
> query parsing and explanation generation. A polite per-city round-robin Kijiji
> scraper feeds a pgvector-indexed Postgres warm store on a nightly launchd
> schedule. User queries hit a SQL hard-filter, then vector rerank on a 60/40
> blend of neighbourhood-fit and listing-fit, then optional PostGIS commute
> filtering, then Claude generates the final answer citing specific listings.
