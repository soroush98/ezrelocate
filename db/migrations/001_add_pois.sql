-- Migration 001: amenity awareness
-- Adds OSM points-of-interest + a denormalised per-listing "nearest amenity"
-- distances map. Idempotent — safe to re-run.

CREATE TABLE IF NOT EXISTS pois (
    id         SERIAL PRIMARY KEY,
    source     TEXT NOT NULL,                    -- 'osm'
    source_id  TEXT NOT NULL,                    -- e.g. 'osm:node:240398754'
    poi_type   TEXT NOT NULL,                    -- 'subway' | 'grocery' | 'cafe' | ...
    name       TEXT,
    location   GEOMETRY(Point, 4326) NOT NULL,
    attrs      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS pois_location_gix ON pois USING GIST (location);
CREATE INDEX IF NOT EXISTS pois_type_idx     ON pois (poi_type);

-- Per-listing nearest-amenity distances in metres, keyed by poi_type.
-- Shape: {"subway":320,"grocery":180,"cafe":90,...}
-- NULL key (or missing) = nothing of that type within the 5km search radius.
ALTER TABLE listings
  ADD COLUMN IF NOT EXISTS amenity_distances_m JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS listings_amenities_gin
  ON listings USING GIN (amenity_distances_m jsonb_path_ops);
