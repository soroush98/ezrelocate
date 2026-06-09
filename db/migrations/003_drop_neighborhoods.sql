-- 003: Drop the neighbourhoods feature.
--
-- The neighbourhoods table was never populated (no loader exists) and
-- listings.neighborhood_id was never assigned, so hybrid retrieval always
-- fell through to listing-only scoring. Removing the dead scaffolding.

DROP INDEX IF EXISTS listings_neighborhood;
ALTER TABLE listings DROP COLUMN IF EXISTS neighborhood_id;
DROP TABLE IF EXISTS neighborhoods;
