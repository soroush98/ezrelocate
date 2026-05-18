-- relocate schema — Canada-wide rentals
--
-- Hybrid retrieval: hard-filter fields live in SQL columns, fuzzy "vibe" text lives
-- in vector embeddings (pgvector). Spatial fields use PostGIS.
--
-- Extensions (postgis, vector, pg_trgm) are created by infra/init/01-extensions.sql
-- when the container starts for the first time.
--
-- This file is destructive — re-running it DROPs and recreates the rental tables.
-- v1 has no real data to preserve; once you go live, switch to versioned migrations
-- (sqitch, alembic, or hand-rolled).

DROP TABLE IF EXISTS pois;
DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS neighborhoods;
DROP TYPE  IF EXISTS listing_status;

-- ---------------------------------------------------------------------------
-- Embedding dimension: Voyage AI voyage-3-large outputs 1024 dims.
-- If you swap providers update both these column types and embeddings.py.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Neighbourhoods — optional per city. Listings without a neighbourhood still
-- work; hybrid retrieval falls back to listing-only scoring.
-- ---------------------------------------------------------------------------
CREATE TABLE neighborhoods (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    city            TEXT NOT NULL,
    province        CHAR(2) NOT NULL,
    boundary        GEOMETRY(MultiPolygon, 4326),
    centroid        GEOMETRY(Point, 4326),
    walk_score      INT,
    transit_score   INT,
    profile_text    TEXT,
    profile_embed   VECTOR(1024),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (province, city, name)
);

CREATE INDEX neighborhoods_boundary_gix    ON neighborhoods USING GIST (boundary);
CREATE INDEX neighborhoods_centroid_gix    ON neighborhoods USING GIST (centroid);
CREATE INDEX neighborhoods_profile_hnsw    ON neighborhoods USING hnsw (profile_embed vector_cosine_ops);
CREATE INDEX neighborhoods_name_trgm       ON neighborhoods USING GIN (name gin_trgm_ops);
CREATE INDEX neighborhoods_city_idx        ON neighborhoods (province, city);

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
    neighborhood_id       INT REFERENCES neighborhoods(id) ON DELETE SET NULL,

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
CREATE INDEX listings_neighborhood   ON listings (neighborhood_id);
CREATE INDEX listings_desc_hnsw      ON listings USING hnsw (desc_embed vector_cosine_ops);
CREATE INDEX listings_last_seen      ON listings (last_seen_at);
CREATE INDEX listings_amenities_gin  ON listings USING GIN (amenity_distances_m jsonb_path_ops);

-- ---------------------------------------------------------------------------
-- POIs — OpenStreetMap amenities (subway, grocery, park, etc.)
-- Loaded by etl/load_osm_pois.py via the Overpass API.
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
