"""Shared ETL helper: asyncpg connection."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import get_settings


@asynccontextmanager
async def connect() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        yield conn
    finally:
        await conn.close()
