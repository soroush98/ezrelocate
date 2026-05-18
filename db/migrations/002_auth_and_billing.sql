-- 002_auth_and_billing.sql
-- Adds anonymous IP quota tracking, Stripe subscription state, and per-user
-- daily query counters.
--
-- Three quota tiers enforced by the backend:
--   1. Anonymous (no JWT)         → 5 queries lifetime per IP (ip_usage)
--   2. Signed-up, not subscribed  → 0 queries (subscriptions.status != 'active')
--   3. Subscribed                 → 50 queries/day  (user_query_log)

-- ---------------------------------------------------------------------------
-- Anonymous IP usage. One row per source IP; query_count monotonically
-- increases. Lifetime quota — we never reset.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ip_usage (
    ip             TEXT PRIMARY KEY,
    query_count    INT NOT NULL DEFAULT 0,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Stripe subscription state, keyed by Supabase auth user id.
-- Webhook updates `status` and `current_period_end`; backend treats a user as
-- "subscribed" only when status='active' AND current_period_end > NOW().
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id                 UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id      TEXT UNIQUE,
    stripe_subscription_id  TEXT UNIQUE,
    status                  TEXT NOT NULL DEFAULT 'none',  -- 'active' | 'canceled' | 'past_due' | 'incomplete' | 'none'
    current_period_end      TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS subscriptions_customer_idx ON subscriptions (stripe_customer_id);
CREATE INDEX IF NOT EXISTS subscriptions_status_idx   ON subscriptions (status);

-- ---------------------------------------------------------------------------
-- Per-user daily query counter. Atomic UPSERT bumps query_count for today;
-- if the resulting value would exceed the limit, the route rejects.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_query_log (
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    day          DATE NOT NULL,
    query_count  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

CREATE INDEX IF NOT EXISTS user_query_log_day_idx ON user_query_log (day);
