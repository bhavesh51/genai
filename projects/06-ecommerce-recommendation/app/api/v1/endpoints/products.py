"""
Project 6 – E-commerce Product Recommendation Engine
Products endpoint: ingest and look up product catalogue entries with embeddings
"""
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db.redis_client import redis_client
from app.recommender.content_based import content_scorer

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────

class ProductIngestRequest(BaseModel):
    product_id: str = Field(..., description="Unique SKU / product identifier")
    title: str = Field(..., max_length=500)
    description: str = Field(..., max_length=5000)
    category: str = Field(..., max_length=200)
    attributes: Dict[str, str] = Field(default_factory=dict, description="Key-value product attributes")
    price: float = Field(0.0, ge=0)
    brand: Optional[str] = None
    image_url: Optional[str] = None


class ProductIngestResponse(BaseModel):
    product_id: str
    status: str
    message: str


class BulkIngestRequest(BaseModel):
    products: List[ProductIngestRequest] = Field(..., min_length=1, max_length=500)


class BulkIngestResponse(BaseModel):
    ingested: int
    failed: int
    errors: List[str] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/products",
    response_model=ProductIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single product into the vector store",
)
async def ingest_product(req: ProductIngestRequest) -> ProductIngestResponse:
    """Embed the product description and upsert into Qdrant."""
    try:
        await content_scorer.embed_and_store_product(
            product_id=req.product_id,
            title=req.title,
            description=req.description,
            attributes=req.attributes,
            category=req.category,
        )
        # Cache product metadata in Redis for fast lookup
        product_meta = req.model_dump()
        await redis_client.set_product_features(req.product_id, product_meta)
    except Exception as exc:
        logger.exception("Failed to ingest product %s", req.product_id)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return ProductIngestResponse(
        product_id=req.product_id,
        status="ok",
        message="Product embedded and stored successfully.",
    )


@router.post(
    "/products/bulk",
    response_model=BulkIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-ingest products into the vector store",
)
async def bulk_ingest_products(req: BulkIngestRequest) -> BulkIngestResponse:
    """Embed and store multiple products; partial failure is reported."""
    ingested, failed = 0, 0
    errors: List[str] = []

    for product in req.products:
        try:
            await content_scorer.embed_and_store_product(
                product_id=product.product_id,
                title=product.title,
                description=product.description,
                attributes=product.attributes,
                category=product.category,
            )
            await redis_client.set_product_features(product.product_id, product.model_dump())
            ingested += 1
        except Exception as exc:
            logger.warning("Failed to ingest %s: %s", product.product_id, exc)
            failed += 1
            errors.append(f"{product.product_id}: {exc}")

    return BulkIngestResponse(ingested=ingested, failed=failed, errors=errors)


@router.get(
    "/products/{product_id}",
    summary="Retrieve cached product metadata",
)
async def get_product(product_id: str) -> dict:
    """Fetch product metadata from the Redis feature store."""
    meta = await redis_client.get_product_features(product_id)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in cache.")
    return meta
