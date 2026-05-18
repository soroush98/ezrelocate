"""Backfill embeddings for listings.desc_embed and neighborhoods.profile_embed.

Re-run any time you add listings or rewrite profiles. Idempotent — only embeds
rows whose embedding column is NULL or whose text has changed.

Run:
    cd backend && python -m etl.embed_all
"""

import asyncio

from app.services.embeddings import embed_texts
from etl._common import connect

BATCH_SIZE = 128         # Voyage standard tier handles big batches comfortably
BATCH_DELAY_SECONDS = 0  # bump >0 if you ever hit RPM limits


async def _embed_table(
    conn, table: str, text_col: str, embed_col: str, where_extra: str = ""
) -> int:
    rows = await conn.fetch(
        f"SELECT id, {text_col} AS text FROM {table} "
        f"WHERE {text_col} IS NOT NULL AND {embed_col} IS NULL {where_extra}"
    )
    if not rows:
        return 0
    total = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        vectors = await embed_texts([r["text"] for r in batch], input_type="document")
        # asyncpg + pgvector: pass the vector as its string form.
        await conn.executemany(
            f"UPDATE {table} SET {embed_col} = $1::vector WHERE id = $2",
            [(_to_pgvector(v), r["id"]) for r, v in zip(batch, vectors, strict=True)],
        )
        total += len(batch)
        print(f"  {table}: {total}/{len(rows)}")
        if start + BATCH_SIZE < len(rows):
            await asyncio.sleep(BATCH_DELAY_SECONDS)
    return total


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def main() -> None:
    async with connect() as conn:
        # Skip stale/removed listings — no point spending tokens on rows we won't serve.
        n_listings = await _embed_table(
            conn, "listings", "description", "desc_embed", "AND status = 'active'"
        )
        n_neigh = await _embed_table(conn, "neighborhoods", "profile_text", "profile_embed")
    print(f"embedded {n_listings} listings, {n_neigh} neighbourhoods ✓")


if __name__ == "__main__":
    asyncio.run(main())
