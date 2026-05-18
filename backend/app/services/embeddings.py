"""Voyage AI embedding wrapper.

Anthropic does not ship a first-party embeddings API; their docs recommend
Voyage AI. ``voyage-3-large`` outputs 1024-dim vectors, which matches the
``VECTOR(1024)`` columns in db/schema.sql.
"""

from typing import Literal

import voyageai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

InputType = Literal["query", "document"]


_client: voyageai.AsyncClient | None = None


def _client_singleton() -> voyageai.AsyncClient:
    global _client
    if _client is None:
        _client = voyageai.AsyncClient(api_key=get_settings().voyage_api_key)
    return _client


@retry(stop=stop_after_attempt(8), wait=wait_exponential(min=4, max=60))
async def embed_texts(
    texts: list[str],
    *,
    input_type: InputType = "document",
) -> list[list[float]]:
    """Embed a batch of texts. ``input_type`` should be 'query' for user prompts
    and 'document' for stored content — Voyage uses different prefixes internally."""
    if not texts:
        return []
    settings = get_settings()
    result = await _client_singleton().embed(
        texts=texts,
        model=settings.voyage_model,
        input_type=input_type,
    )
    return result.embeddings


async def embed_query(text: str) -> list[float]:
    [vec] = await embed_texts([text], input_type="query")
    return vec
