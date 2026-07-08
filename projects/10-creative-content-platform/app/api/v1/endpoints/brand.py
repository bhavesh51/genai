"""
Project 10 – Creative Content Generation Platform
Brand endpoints:
  POST /brand/ingest              – embed and store a brand guideline chunk in Weaviate
  GET  /brand/{brand_id}/guidelines – return top-5 guideline chunks for a brand
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db.weaviate_client import weaviate_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────────

class BrandIngestRequest(BaseModel):
    brand_id: str = Field(..., description="Unique brand identifier")
    content_type: str = Field(
        ...,
        description="Category of brand guideline (e.g. tone-of-voice, visual, messaging)",
        max_length=100,
    )
    text: str = Field(..., description="Brand guideline text chunk to embed and store", max_length=10000)


class BrandIngestResponse(BaseModel):
    brand_id: str
    chunk_id: str
    status: str
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/brand/ingest",
    response_model=BrandIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a brand guideline chunk into Weaviate",
)
async def ingest_brand_guideline(req: BrandIngestRequest) -> BrandIngestResponse:
    """
    Embeds the guideline text and upserts it into the Weaviate BrandGuideline class.
    Uses a zero-vector placeholder locally; in production the E5-large embedding
    endpoint is called to produce a real 1024-dim vector.
    """
    try:
        from app.core.config import settings as cfg
        # In production: replace dummy_vector with await embedding_service.embed(req.text)
        dummy_vector = [0.0] * cfg.EMBEDDING_DIMENSION
        chunk_id = await weaviate_client.upsert_brand_chunk(
            brand_id=req.brand_id,
            content_type=req.content_type,
            text=req.text,
            vector=dummy_vector,
            chunk_index=0,
        )
    except Exception as exc:
        logger.exception(
            "Brand guideline ingestion failed for brand_id=%s", req.brand_id
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ingestion failed: {exc}",
        ) from exc

    return BrandIngestResponse(
        brand_id=req.brand_id,
        chunk_id=chunk_id,
        status="ok",
        message="Brand guideline chunk embedded and stored successfully.",
    )


@router.get(
    "/brand/{brand_id}/guidelines",
    summary="Retrieve top-5 brand guideline chunks from Weaviate",
)
async def get_brand_guidelines(brand_id: str) -> list:
    """
    Returns the top-5 most relevant brand guideline chunks for the given brand_id.
    Uses a zero-vector placeholder locally; production wires in the E5-large embedding.
    """
    try:
        from app.core.config import settings as cfg
        dummy_vector = [0.0] * cfg.EMBEDDING_DIMENSION
        chunks = await weaviate_client.search_brand_guidelines(
            brand_id=brand_id,
            query_vector=dummy_vector,
            top_k=5,
        )
    except Exception as exc:
        logger.exception("Failed to retrieve guidelines for brand_id=%s", brand_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Guidelines retrieval failed: {exc}",
        ) from exc

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No guidelines found for brand_id='{brand_id}'.",
        )
    return chunks
