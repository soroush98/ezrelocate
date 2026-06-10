"""Full-text query logging for /api/query.

Writes the actual query string and its outcome to the `query_log` table. This
is separate from quota tracking (services/quota.py), which stores only counts.

Logging is best-effort: a failure here must never break the user's request, so
record_query swallows and logs its own exceptions rather than propagating them.
"""

import logging

from app.db import acquire
from app.services.quota import QuotaContext

logger = logging.getLogger(__name__)


async def record_query(
    ctx: QuotaContext,
    query: str,
    *,
    out_of_scope: bool,
    listing_count: int,
) -> None:
    """Persist one query and its outcome. Never raises."""
    try:
        async with acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_log
                    (user_id, ip, tier, query, out_of_scope, listing_count)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                ctx.user_id,
                ctx.ip,
                ctx.tier.value,
                query,
                out_of_scope,
                listing_count,
            )
    except Exception:  # noqa: BLE001 — logging must not break the request
        logger.exception("failed to record query_log row")
