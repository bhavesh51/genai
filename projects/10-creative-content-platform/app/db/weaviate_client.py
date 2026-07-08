"""
Project 10 – Creative Content Generation Platform
Weaviate v4 async client wrapper for brand guidelines and creative assets
"""
import logging
import uuid
from typing import List, Optional

import weaviate
import weaviate.classes as wvc
from weaviate.client import WeaviateAsyncClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class WeaviateClientWrapper:
    """Thin async wrapper around the official Weaviate v4 client."""

    def __init__(self) -> None:
        self._client: Optional[WeaviateAsyncClient] = None

    async def connect(self) -> None:
        """Open connection and ensure schema classes exist."""
        auth = (
            weaviate.auth.AuthApiKey(api_key=settings.WEAVIATE_API_KEY)
            if settings.WEAVIATE_API_KEY
            else None
        )
        self._client = weaviate.use_async_with_custom(
            http_host=settings.WEAVIATE_HOST,
            http_port=settings.WEAVIATE_PORT,
            http_secure=False,
            grpc_host=settings.WEAVIATE_HOST,
            grpc_port=50051,
            grpc_secure=False,
            auth_credentials=auth,
        )
        await self._client.connect()
        await self._ensure_classes()
        logger.info(
            "Connected to Weaviate at %s:%s",
            settings.WEAVIATE_HOST,
            settings.WEAVIATE_PORT,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("Weaviate connection closed")

    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected()

    # ── Schema helpers ─────────────────────────────────────────────────────────

    async def _ensure_classes(self) -> None:
        """Create BrandGuideline and CreativeAsset classes if they do not exist."""
        existing = await self._client.collections.list_all()
        existing_names = list(existing.keys())

        if settings.WEAVIATE_BRAND_CLASS not in existing_names:
            await self._client.collections.create(
                name=settings.WEAVIATE_BRAND_CLASS,
                vectorizer_config=wvc.config.Configure.Vectorizer.none(),
                properties=[
                    wvc.config.Property(name="brand_id", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="content_type", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="chunk_index", data_type=wvc.config.DataType.INT),
                ],
            )
            logger.info("Created Weaviate class '%s'", settings.WEAVIATE_BRAND_CLASS)

        if settings.WEAVIATE_ASSET_CLASS not in existing_names:
            await self._client.collections.create(
                name=settings.WEAVIATE_ASSET_CLASS,
                vectorizer_config=wvc.config.Configure.Vectorizer.none(),
                properties=[
                    wvc.config.Property(name="asset_id", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="brand_id", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="content_type", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="approved", data_type=wvc.config.DataType.BOOL),
                ],
            )
            logger.info("Created Weaviate class '%s'", settings.WEAVIATE_ASSET_CLASS)

    # ── Brand guideline operations ─────────────────────────────────────────────

    async def upsert_brand_chunk(
        self,
        brand_id: str,
        content_type: str,
        text: str,
        vector: List[float],
        chunk_index: int = 0,
    ) -> str:
        """Insert or update a brand guideline chunk; returns the Weaviate UUID."""
        collection = self._client.collections.get(settings.WEAVIATE_BRAND_CLASS)
        object_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{brand_id}:{content_type}:{chunk_index}"))
        await collection.data.insert(
            properties={
                "brand_id": brand_id,
                "content_type": content_type,
                "text": text,
                "chunk_index": chunk_index,
            },
            vector=vector,
            uuid=object_id,
        )
        logger.debug("Upserted brand chunk %s for brand_id=%s", object_id, brand_id)
        return object_id

    async def search_brand_guidelines(
        self,
        brand_id: str,
        query_vector: List[float],
        top_k: int = 5,
    ) -> List[dict]:
        """Return top-k brand guideline chunks for a given brand_id."""
        collection = self._client.collections.get(settings.WEAVIATE_BRAND_CLASS)
        response = await collection.query.near_vector(
            near_vector=query_vector,
            limit=top_k,
            filters=wvc.query.Filter.by_property("brand_id").equal(brand_id),
            return_properties=["brand_id", "content_type", "text", "chunk_index"],
        )
        return [
            {
                "brand_id": obj.properties.get("brand_id"),
                "content_type": obj.properties.get("content_type"),
                "text": obj.properties.get("text"),
                "chunk_index": obj.properties.get("chunk_index"),
                "score": obj.metadata.certainty if obj.metadata else None,
            }
            for obj in response.objects
        ]

    # ── Creative asset operations ──────────────────────────────────────────────

    async def upsert_asset(
        self,
        asset_id: str,
        brand_id: str,
        content_type: str,
        content: str,
        vector: List[float],
        approved: bool = False,
    ) -> str:
        """Insert or update a creative asset in Weaviate; returns UUID."""
        collection = self._client.collections.get(settings.WEAVIATE_ASSET_CLASS)
        object_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, asset_id))
        await collection.data.insert(
            properties={
                "asset_id": asset_id,
                "brand_id": brand_id,
                "content_type": content_type,
                "content": content,
                "approved": approved,
            },
            vector=vector,
            uuid=object_id,
        )
        logger.debug("Upserted asset %s for brand_id=%s", asset_id, brand_id)
        return object_id

    async def search_assets(
        self,
        query_vector: List[float],
        top_k: int = 10,
        brand_id: Optional[str] = None,
    ) -> List[dict]:
        """Semantic search over the creative asset index."""
        collection = self._client.collections.get(settings.WEAVIATE_ASSET_CLASS)
        query_filter = None
        if brand_id:
            query_filter = wvc.query.Filter.by_property("brand_id").equal(brand_id)

        response = await collection.query.near_vector(
            near_vector=query_vector,
            limit=top_k,
            filters=query_filter,
            return_properties=["asset_id", "brand_id", "content_type", "content", "approved"],
        )
        return [
            {
                "asset_id": obj.properties.get("asset_id"),
                "brand_id": obj.properties.get("brand_id"),
                "content_type": obj.properties.get("content_type"),
                "content": obj.properties.get("content"),
                "approved": obj.properties.get("approved"),
                "score": obj.metadata.certainty if obj.metadata else None,
            }
            for obj in response.objects
        ]


weaviate_client = WeaviateClientWrapper()
