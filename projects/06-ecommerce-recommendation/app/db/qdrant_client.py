"""
Project 6 – E-commerce Product Recommendation Engine
Qdrant async client wrapper for product vector operations
"""
import logging
from typing import List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    SearchRequest,
    VectorParams,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantClientWrapper:
    """Thin async wrapper around the official Qdrant client."""

    def __init__(self) -> None:
        self._client: Optional[AsyncQdrantClient] = None

    async def connect(self) -> None:
        self._client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            https=bool(settings.QDRANT_API_KEY),
        )
        await self._ensure_collection()
        logger.info("Connected to Qdrant at %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("Qdrant connection closed")

    def is_connected(self) -> bool:
        return self._client is not None

    async def _ensure_collection(self) -> None:
        """Create collection if it does not exist yet."""
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if settings.QDRANT_COLLECTION not in names:
            await self._client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s'", settings.QDRANT_COLLECTION)

    async def upsert_product(self, product_id: str, vector: List[float], payload: dict) -> None:
        """Insert or update a product embedding."""
        await self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[PointStruct(id=product_id, vector=vector, payload=payload)],
        )

    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 20,
        category_filter: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """Return similar products with optional category filter and exclusion list."""
        must_conditions = []
        must_not_conditions = []

        if category_filter:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category_filter))
            )
        if exclude_ids:
            for pid in exclude_ids:
                must_not_conditions.append(
                    FieldCondition(key="product_id", match=MatchValue(value=pid))
                )

        query_filter = None
        if must_conditions or must_not_conditions:
            query_filter = Filter(must=must_conditions or None, must_not=must_not_conditions or None)

        results = await self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {
                "product_id": hit.payload.get("product_id", str(hit.id)),
                "score": hit.score,
                **hit.payload,
            }
            for hit in results
        ]


qdrant_client = QdrantClientWrapper()
