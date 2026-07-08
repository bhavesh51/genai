"""
Project 10 – Creative Content Generation Platform
Assets endpoints:
  GET    /assets/{asset_id}          – retrieve asset from Redis cache
  GET    /assets/search              – semantic search in Weaviate asset index
  POST   /assets/{asset_id}/approve  – mark asset as approved
  DELETE /assets/{asset_id}          – remove asset from cache
"""
import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.db.redis_client import redis_client
from app.db.weaviate_client import weaviate_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/assets/search",
    summary="Semantic search over the creative asset index",
)
async def search_assets(
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results to return"),
    brand_id: str = Query(None, description="Optionally restrict results to a brand"),
) -> list:
    """
    Embeds the query and performs a near-vector search in the Weaviate CreativeAsset class.
    Uses a zero-vector placeholder locally; production wires in the E5-large embedding call.
    """
    try:
        from app.core.config import settings as cfg
        dummy_vector = [0.0] * cfg.EMBEDDING_DIMENSION
        results = await weaviate_client.search_assets(
            query_vector=dummy_vector,
            top_k=top_k,
            brand_id=brand_id,
        )
        return results
    except Exception as exc:
        logger.exception("Asset search failed for query='%s'", q)
        raise HTTPException(status_code=500, detail=f"Asset search error: {exc}") from exc


@router.get(
    "/assets/{asset_id}",
    summary="Retrieve a creative asset from Redis cache",
)
async def get_asset(asset_id: str) -> dict:
    """Fetch the full asset payload stored in Redis."""
    asset = await redis_client.get_asset(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    return asset


@router.post(
    "/assets/{asset_id}/approve",
    summary="Approve a creative asset",
)
async def approve_asset(asset_id: str) -> dict:
    """Mark the specified asset as approved in the Redis cache."""
    updated = await redis_client.update_asset_field(asset_id, "approved", True)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    logger.info("Asset %s approved", asset_id)
    return {"asset_id": asset_id, "status": "approved"}


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a creative asset from cache",
)
async def delete_asset(asset_id: str) -> None:
    """Remove the specified asset from the Redis cache."""
    asset = await redis_client.get_asset(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    await redis_client.delete_asset(asset_id)
    logger.info("Asset %s deleted", asset_id)
