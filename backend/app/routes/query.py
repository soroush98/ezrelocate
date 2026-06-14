from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.models import RecommendationResponse
from app.services.auth import AuthUser, get_client_ip, optional_user
from app.services.llm import generate_recommendation, parse_query
from app.services.query_log import record_query
from app.services.quota import enforce_query_quota
from app.services.retrieval import retrieve

router = APIRouter()

# Cap incoming queries so a single request can't blow up the LLM token bill.
# 600 chars comfortably fits any plausible rental description in plain English.
MAX_QUERY_CHARS = 600


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)


_DEFAULT_REJECTION = (
    "I can only help with searches for residential rentals in Canada. "
    "Try something like: \"Toronto, 1 bedroom under $2500, pet-friendly, near a subway\"."
)


@router.post("/query", response_model=RecommendationResponse)
async def query(
    req: QueryRequest,
    request: Request,
    user: AuthUser | None = Depends(optional_user),
) -> RecommendationResponse:
    # Quota gate runs BEFORE any LLM/embedding spend. Raises 402/429 on rejection.
    ctx = await enforce_query_quota(user, get_client_ip(request))

    try:
        parsed = await parse_query(req.query)

        if parsed.out_of_scope:
            await record_query(ctx, req.query, out_of_scope=True, listing_count=0)
            return RecommendationResponse(
                query=req.query,
                parsed=parsed,
                listings=[],
                reasoning=parsed.rejection_reason or _DEFAULT_REJECTION,
            )

        listings = await retrieve(parsed)
        reasoning = (
            await generate_recommendation(req.query, parsed, listings)
            if listings
            else (
                "No listings match those hard filters — "
                "try widening the price range or bedroom count."
            )
        )
    except TimeoutError:
        # An upstream (Claude / Voyage) blew its per-request deadline. Surface a
        # retryable 503 rather than a 500 — the quota increment already happened,
        # but a timed-out search shouldn't read as a successful one.
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_timeout",
                "message": "Search took too long to respond — please try again.",
            },
        ) from None

    await record_query(ctx, req.query, out_of_scope=False, listing_count=len(listings))
    return RecommendationResponse(
        query=req.query,
        parsed=parsed,
        listings=listings,
        reasoning=reasoning,
    )
