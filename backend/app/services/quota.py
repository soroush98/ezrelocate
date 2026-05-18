"""Quota gates for /api/query.

Tiers (in priority order):
  1. Subscriber       → SUBSCRIBER_DAILY_LIMIT queries/day (from settings)
  2. Signed-up        → 0 queries. Must subscribe.
  3. Anonymous (IP)   → ANON_IP_LIFETIME_LIMIT queries lifetime per IP.

Each gate atomically check-and-increments using `INSERT ... ON CONFLICT ...
DO UPDATE ... WHERE ... RETURNING`. If RETURNING is empty, the user is at or
over the limit and the call is rejected — no LLM tokens spent.
"""

from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException

from app.config import get_settings
from app.db import acquire
from app.services.auth import AuthUser


class Tier(str, Enum):
    ANONYMOUS = "anonymous"
    SIGNED_UP = "signed_up"
    SUBSCRIBED = "subscribed"


@dataclass(frozen=True)
class QuotaContext:
    tier: Tier
    user_id: str | None
    ip: str


async def _get_subscription_status(user_id: str) -> bool:
    """True iff the user has an active, in-period Stripe subscription."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, current_period_end
              FROM subscriptions
             WHERE user_id = $1
            """,
            user_id,
        )
    if not row:
        return False
    if row["status"] != "active":
        return False
    cpe = row["current_period_end"]
    if cpe is None:
        return False
    # Compare in UTC; asyncpg returns timezone-aware datetimes.
    from datetime import datetime, timezone
    return cpe > datetime.now(timezone.utc)


async def enforce_query_quota(user: AuthUser | None, ip: str) -> QuotaContext:
    """Check and atomically increment the appropriate quota.

    Raises HTTPException(402) when the caller must sign up or subscribe.
    Raises HTTPException(429) when a subscriber has hit their daily cap.
    Returns the caller's tier on success.
    """
    settings = get_settings()

    # --- Authed path -------------------------------------------------------
    if user is not None:
        subscribed = await _get_subscription_status(user.user_id)
        if not subscribed:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "subscription_required",
                    "message": "Subscribe to keep searching — 50 queries/day.",
                },
            )
        # Subscribed → bump today's counter.
        async with acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_query_log (user_id, day, query_count)
                VALUES ($1, CURRENT_DATE, 1)
                ON CONFLICT (user_id, day) DO UPDATE
                  SET query_count = user_query_log.query_count + 1
                  WHERE user_query_log.query_count < $2
                RETURNING query_count
                """,
                user.user_id,
                settings.subscriber_daily_limit,
            )
        if row is None:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "daily_limit_reached",
                    "message": (
                        f"You've used your {settings.subscriber_daily_limit} queries "
                        "for today — resets at midnight UTC."
                    ),
                },
            )
        return QuotaContext(tier=Tier.SUBSCRIBED, user_id=user.user_id, ip=ip)

    # --- Anonymous path ----------------------------------------------------
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ip_usage (ip, query_count, last_seen_at)
            VALUES ($1, 1, NOW())
            ON CONFLICT (ip) DO UPDATE
              SET query_count = ip_usage.query_count + 1,
                  last_seen_at = NOW()
              WHERE ip_usage.query_count < $2
            RETURNING query_count
            """,
            ip,
            settings.anon_ip_lifetime_limit,
        )
    if row is None:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "signup_required",
                "message": (
                    f"You've used your {settings.anon_ip_lifetime_limit} free searches. "
                    "Sign up and subscribe to continue."
                ),
            },
        )
    return QuotaContext(tier=Tier.ANONYMOUS, user_id=None, ip=ip)
