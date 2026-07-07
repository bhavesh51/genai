"""
Project 6 – E-commerce Product Recommendation Engine
Recommendations endpoint: POST /recommend and GET /recommend/{user_id}
"""
import hashlib
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.db.redis_client import redis_client
from app.recommender.hybrid import hybrid_recommender

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user")
    user_profile: str = Field(
        ...,
        description="Natural-language summary of the user's preferences and recent activity",
        max_length=2000,
    )
    category_filter: Optional[str] = Field(None, description="Restrict recommendations to this category")
    purchased_ids: List[str] = Field(default_factory=list, description="Product IDs already purchased (exclude)")
    use_llm: bool = Field(True, description="Whether to apply LLM reranking")
    top_k: int = Field(20, ge=5, le=100, description="Number of candidates to retrieve")
    final_n: int = Field(10, ge=1, le=50, description="Number of recommendations to return")


class RecommendedItem(BaseModel):
    product_id: str
    title: str = ""
    category: str = ""
    hybrid_score: float


class RecommendResponse(BaseModel):
    user_id: str
    recommendations: List[RecommendedItem]
    rationale: str
    strategy: str
    cached: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/recommend",
    response_model=RecommendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get personalised product recommendations",
)
async def get_recommendations(req: RecommendRequest) -> RecommendResponse:
    """
    Returns a ranked list of personalised product recommendations using the
    hybrid ALS + content-based + LLM pipeline.
    """
    # Build a deterministic cache key from request parameters
    raw_key = f"{req.user_id}:{req.user_profile}:{req.category_filter}:{req.use_llm}:{req.final_n}"
    cache_key = hashlib.md5(raw_key.encode()).hexdigest()

    cached = await redis_client.get_recommendations(cache_key)
    if cached:
        return RecommendResponse(**cached, cached=True)

    try:
        result = await hybrid_recommender.recommend(
            user_id=req.user_id,
            user_profile=req.user_profile,
            category_filter=req.category_filter,
            purchased_ids=req.purchased_ids,
            use_llm=req.use_llm,
            top_k=req.top_k,
            final_n=req.final_n,
        )
    except Exception as exc:
        logger.exception("Recommendation pipeline error for user %s", req.user_id)
        raise HTTPException(status_code=500, detail="Recommendation service error") from exc

    response = RecommendResponse(
        user_id=result["user_id"],
        recommendations=[RecommendedItem(**item) for item in result["recommendations"]],
        rationale=result["rationale"],
        strategy=result["strategy"],
    )

    await redis_client.set_recommendations(cache_key, response.model_dump(), ttl=300)
    return response


@router.get(
    "/recommend/{user_id}",
    response_model=RecommendResponse,
    summary="Quick recommendations using stored user profile",
)
async def get_quick_recommendations(
    user_id: str,
    category: Optional[str] = Query(None, description="Restrict to category"),
    n: int = Query(10, ge=1, le=50, description="Number of results"),
) -> RecommendResponse:
    """
    Light-weight endpoint that pulls user features from Redis and delegates
    to the hybrid recommender using a default ALS-first strategy (no LLM).
    """
    features = await redis_client.get_user_features(user_id)
    if not features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored profile for user '{user_id}'. Use POST /recommend instead.",
        )

    profile_text = features.get("preference_summary", "general interest in products")
    result = await hybrid_recommender.recommend(
        user_id=user_id,
        user_profile=profile_text,
        category_filter=category,
        use_llm=False,
        final_n=n,
    )
    return RecommendResponse(
        user_id=result["user_id"],
        recommendations=[RecommendedItem(**item) for item in result["recommendations"]],
        rationale=result["rationale"],
        strategy=result["strategy"],
    )
