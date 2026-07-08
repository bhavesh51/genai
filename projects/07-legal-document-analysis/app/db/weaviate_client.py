"""
Project 7 – Legal Document Analysis & Contract Intelligence
Async Weaviate v4 client wrapper for legal clause vector operations
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.query import Filter

from app.core.config import settings

logger = logging.getLogger(__name__)


class WeaviateClientWrapper:
    """Thin async-compatible wrapper around the Weaviate v4 client."""

    def __init__(self) -> None:
        self._client: Optional[weaviate.WeaviateClient] = None

    async def connect(self) -> None:
        """Connect to Weaviate and ensure the LegalClause collection exists."""
        auth = (
            weaviate.auth.AuthApiKey(settings.WEAVIATE_API_KEY)
            if settings.WEAVIATE_API_KEY
            else None
        )
        self._client = weaviate.connect_to_custom(
            http_host=settings.WEAVIATE_HOST,
            http_port=settings.WEAVIATE_PORT,
            http_secure=bool(settings.WEAVIATE_API_KEY),
            grpc_host=settings.WEAVIATE_HOST,
            grpc_port=50051,
            grpc_secure=bool(settings.WEAVIATE_API_KEY),
            auth_credentials=auth,
        )
        await self._ensure_collection()
        logger.info(
            "Connected to Weaviate at %s:%s",
            settings.WEAVIATE_HOST,
            settings.WEAVIATE_PORT,
        )

    async def close(self) -> None:
        if self._client:
            self._client.close()
            logger.info("Weaviate connection closed")

    def is_connected(self) -> bool:
        return self._client is not None

    async def _ensure_collection(self) -> None:
        """Create the LegalClause collection if it does not exist."""
        if self._client.collections.exists(settings.WEAVIATE_CLASS):
            return
        self._client.collections.create(
            name=settings.WEAVIATE_CLASS,
            description="Legal contract clause with risk metadata",
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
            ),
            properties=[
                Property(name="clause_id", data_type=DataType.TEXT),
                Property(name="document_id", data_type=DataType.TEXT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="char_start", data_type=DataType.INT),
                Property(name="risk_category", data_type=DataType.TEXT),
                Property(name="risk_score", data_type=DataType.NUMBER),
                Property(name="explanation", data_type=DataType.TEXT),
                Property(name="page", data_type=DataType.INT),
            ],
        )
        logger.info("Created Weaviate collection '%s'", settings.WEAVIATE_CLASS)

    async def upsert_clause(
        self,
        clause_id: str,
        document_id: str,
        text: str,
        char_start: int,
        vector: List[float],
        risk_category: str = "",
        risk_score: float = 0.0,
        explanation: str = "",
        page: int = 0,
    ) -> str:
        """Insert or update a clause object with its embedding vector."""
        collection = self._client.collections.get(settings.WEAVIATE_CLASS)
        # Use a deterministic UUID derived from the clause_id
        obj_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, clause_id))
        properties: Dict[str, Any] = {
            "clause_id": clause_id,
            "document_id": document_id,
            "text": text,
            "char_start": char_start,
            "risk_category": risk_category,
            "risk_score": risk_score,
            "explanation": explanation,
            "page": page,
        }
        collection.data.insert(
            properties=properties,
            vector=vector,
            uuid=obj_uuid,
        )
        return obj_uuid

    async def search_clauses(
        self,
        query_vector: List[float],
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over clauses with optional document_id filter."""
        collection = self._client.collections.get(settings.WEAVIATE_CLASS)

        query_filter = None
        if document_id:
            query_filter = Filter.by_property("document_id").equal(document_id)

        results = collection.query.near_vector(
            near_vector=query_vector,
            limit=top_k,
            filters=query_filter,
            return_metadata=wvc.query.MetadataQuery(distance=True),
        )

        return [
            {
                "clause_id": obj.properties.get("clause_id", ""),
                "document_id": obj.properties.get("document_id", ""),
                "text": obj.properties.get("text", ""),
                "char_start": obj.properties.get("char_start", 0),
                "risk_category": obj.properties.get("risk_category", ""),
                "risk_score": obj.properties.get("risk_score", 0.0),
                "explanation": obj.properties.get("explanation", ""),
                "page": obj.properties.get("page", 0),
                "distance": obj.metadata.distance if obj.metadata else None,
            }
            for obj in results.objects
        ]

    async def search_by_document_id(self, document_id: str) -> List[Dict[str, Any]]:
        """Retrieve all clauses belonging to a given document."""
        collection = self._client.collections.get(settings.WEAVIATE_CLASS)
        results = collection.query.fetch_objects(
            filters=Filter.by_property("document_id").equal(document_id),
            limit=500,
        )
        return [
            {
                "clause_id": obj.properties.get("clause_id", ""),
                "document_id": obj.properties.get("document_id", ""),
                "text": obj.properties.get("text", ""),
                "char_start": obj.properties.get("char_start", 0),
                "risk_category": obj.properties.get("risk_category", ""),
                "risk_score": obj.properties.get("risk_score", 0.0),
                "explanation": obj.properties.get("explanation", ""),
                "page": obj.properties.get("page", 0),
            }
            for obj in results.objects
        ]


weaviate_client = WeaviateClientWrapper()
