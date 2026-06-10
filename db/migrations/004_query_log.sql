-- 004_query_log.sql
-- Full-text log of every /api/query call (the actual query string + outcome).
--
-- Distinct from user_query_log / ip_usage, which store only aggregate COUNTS
-- for quota enforcement. This table stores the query TEXT for analytics and
-- debugging. Privacy note: this is user-provided search text — keep a sane
-- retention policy (see retention purge at the bottom) and disclose in the
-- privacy policy.

CREATE TABLE IF NOT EXISTS query_log (
    id             BIGSERIAL PRIMARY KEY,
    -- NULL for anonymous callers. SET NULL (not CASCADE) so deleting a user
    -- de-identifies their rows without losing the aggregate analytics value.
    user_id        UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ip             TEXT NOT NULL,
    tier           TEXT NOT NULL,                 -- 'anonymous' | 'signed_up' | 'subscribed'
    query          TEXT NOT NULL,
    out_of_scope   BOOLEAN NOT NULL DEFAULT FALSE,
    listing_count  INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS query_log_created_at_idx ON query_log (created_at);
CREATE INDEX IF NOT EXISTS query_log_user_id_idx    ON query_log (user_id);

-- Optional retention purge (run on a schedule, e.g. nightly):
--   DELETE FROM query_log WHERE created_at < NOW() - INTERVAL '90 days';
