-- relocate schema — Canada-wide rentals
--
-- Hybrid retrieval: hard-filter fields live in SQL columns, fuzzy "vibe" text lives
-- in vector embeddings (pgvector). Spatial fields use PostGIS.
--
-- Extensions (postgis, vector, pg_trgm) are created by infra/init/01-extensions.sql
-- when the container starts for the first time.
--
-- This file is the single source of truth for the schema. It is destructive —
-- re-running it DROPs and recreates the rental tables — so only run it against a
-- fresh/local database (init_db.sh), never production. Apply incremental changes
-- to prod by hand, then fold them back in here.
--
-- Auth/billing/usage tables reference Supabase's auth.users. On Supabase that
-- schema already exists; locally we create a minimal stub below so the foreign
-- keys resolve and init_db.sh works against the plain Postgres container.

DROP TABLE IF EXISTS query_log;
DROP TABLE IF EXISTS user_query_log;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS ip_usage;
DROP TABLE IF EXISTS pois;
DROP TABLE IF EXISTS listings;
DROP TYPE  IF EXISTS listing_status;

-- ---------------------------------------------------------------------------
-- Embedding dimension: Voyage AI voyage-3-large outputs 1024 dims.
-- If you swap providers update both these column types and embeddings.py.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Listings — rentals from Kijiji, rentals.ca, ...
-- ---------------------------------------------------------------------------
CREATE TYPE listing_status AS ENUM ('active', 'stale', 'removed');

CREATE TABLE listings (
    id                    SERIAL PRIMARY KEY,
    source                TEXT NOT NULL,                  -- 'kijiji' | 'rentals_ca' | ...
    source_id             TEXT NOT NULL,                  -- the source's listing id
    url                   TEXT NOT NULL,
    title                 TEXT,
    address               TEXT,
    city                  TEXT NOT NULL,
    province              CHAR(2) NOT NULL,
    postal_code           TEXT,
    location              GEOMETRY(Point, 4326),          -- nullable: some sources omit coords

    -- Rental specifics
    monthly_rent          INT,                            -- CAD/month
    bedrooms              NUMERIC(3, 1),                  -- 0.5 = bachelor/studio
    bathrooms             NUMERIC(3, 1),
    sqft                  INT,
    property_type         TEXT,                           -- 'apartment' | 'house' | 'condo' | 'townhouse' | 'basement' | 'room'
    furnished             BOOLEAN,
    pet_friendly          BOOLEAN,
    utilities_included    TEXT[] NOT NULL DEFAULT '{}',   -- e.g. {'heat','water','internet'}
    lease_length_months   INT,                            -- NULL = unspecified / month-to-month
    available_from        DATE,

    description           TEXT,
    desc_embed            VECTOR(1024),

    -- Per-listing nearest-amenity distances in metres, keyed by poi_type.
    -- Populated by etl/compute_amenity_distances.py after OSM POI ingest.
    amenity_distances_m   JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Lifecycle / staleness
    status                listing_status NOT NULL DEFAULT 'active',
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source, source_id)
);

CREATE INDEX listings_location_gix   ON listings USING GIST (location);
CREATE INDEX listings_filter_idx     ON listings (status, province, city, monthly_rent, bedrooms);
CREATE INDEX listings_desc_hnsw      ON listings USING hnsw (desc_embed vector_cosine_ops);
CREATE INDEX listings_last_seen      ON listings (last_seen_at);
CREATE INDEX listings_amenities_gin  ON listings USING GIN (amenity_distances_m jsonb_path_ops);

-- ---------------------------------------------------------------------------
-- POIs — OpenStreetMap amenities (subway, grocery, park, etc.)
-- Loaded by etl/load_osm_pois_geofabrik.py from offline Geofabrik extracts.
-- ---------------------------------------------------------------------------
CREATE TABLE pois (
    id         SERIAL PRIMARY KEY,
    source     TEXT NOT NULL,
    source_id  TEXT NOT NULL,
    poi_type   TEXT NOT NULL,
    name       TEXT,
    location   GEOMETRY(Point, 4326) NOT NULL,
    attrs      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id)
);

CREATE INDEX pois_location_gix ON pois USING GIST (location);
CREATE INDEX pois_type_idx     ON pois (poi_type);

-- ===========================================================================
-- Auth, billing & usage
--
-- These tables reference Supabase's auth.users. On Supabase that schema and
-- table already exist, so the statements below are no-ops there. Locally we
-- create a minimal stub so the foreign keys resolve and init_db.sh succeeds.
-- ===========================================================================
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY);

-- Three quota tiers enforced by the backend (services/quota.py):
--   1. Anonymous (no JWT)         → 5 queries lifetime per IP   (ip_usage)
--   2. Signed-up, not subscribed  → 0 queries                  (subscriptions)
--   3. Subscribed                 → 50 queries/day              (user_query_log)

-- Anonymous IP usage. One row per source IP; query_count monotonically
-- increases. Lifetime quota — we never reset.
CREATE TABLE ip_usage (
    ip             TEXT PRIMARY KEY,
    query_count    INT NOT NULL DEFAULT 0,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Stripe subscription state, keyed by Supabase auth user id. The webhook updates
-- `status` and `current_period_end`; the backend treats a user as "subscribed"
-- only when status='active' AND current_period_end > NOW().
CREATE TABLE subscriptions (
    user_id                 UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id      TEXT UNIQUE,
    stripe_subscription_id  TEXT UNIQUE,
    status                  TEXT NOT NULL DEFAULT 'none',  -- 'active' | 'canceled' | 'past_due' | 'incomplete' | 'none'
    current_period_end      TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX subscriptions_customer_idx ON subscriptions (stripe_customer_id);
CREATE INDEX subscriptions_status_idx   ON subscriptions (status);

-- Per-user daily query counter. Atomic UPSERT bumps query_count for today; if
-- the resulting value would exceed the limit, the route rejects.
CREATE TABLE user_query_log (
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    day          DATE NOT NULL,
    query_count  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

CREATE INDEX user_query_log_day_idx ON user_query_log (day);

-- Full-text log of every /api/query call (the actual query string + outcome),
-- distinct from the aggregate counters above. user_id is NULL for anonymous
-- callers; ON DELETE SET NULL de-identifies a deleted user's rows without
-- losing their analytics value. Keep a retention policy (see purge below).
CREATE TABLE query_log (
    id             BIGSERIAL PRIMARY KEY,
    user_id        UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ip             TEXT NOT NULL,
    tier           TEXT NOT NULL,                 -- 'anonymous' | 'signed_up' | 'subscribed'
    query          TEXT NOT NULL,
    out_of_scope   BOOLEAN NOT NULL DEFAULT FALSE,
    listing_count  INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX query_log_created_at_idx ON query_log (created_at);
CREATE INDEX query_log_user_id_idx    ON query_log (user_id);

-- Optional retention purge (run on a schedule, e.g. nightly):
--   DELETE FROM query_log WHERE created_at < NOW() - INTERVAL '90 days';
