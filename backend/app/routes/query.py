from fastapi import APIRouter
from pydantic import BaseModel

from app.models import RecommendationResponse
from app.services.llm import generate_recommendation, parse_query
from app.services.retrieval import retrieve

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


@router.post("/query", response_model=RecommendationResponse)
async def query(req: QueryRequest) -> RecommendationResponse:
    parsed = await parse_query(req.query)
    listings = await retrieve(parsed)
    reasoning = (
        await generate_recommendation(req.query, parsed, listings)
        if listings
        else "No listings match those hard filters — try widening the price range or bedroom count."
    )
    return RecommendationResponse(
        query=req.query,
        parsed=parsed,
        listings=listings,
        reasoning=reasoning,
    )
