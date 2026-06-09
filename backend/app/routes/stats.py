from fastapi import APIRouter

from app.db import acquire

router = APIRouter()


@router.get("/stats")
async def stats() -> dict[str, int]:
    """Live corpus size for the UI.

    Counts the listings pgvector can actually rank — active and embedded — so
    the number shown in the UI matches what a query searches over (see the
    retrieval hard-filter: status='active' AND desc_embed IS NOT NULL).
    """
    async with acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM listings "
            "WHERE status = 'active' AND desc_embed IS NOT NULL"
        )
    return {"listings": int(count or 0)}
