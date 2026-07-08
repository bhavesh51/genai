"""
Project 9 – Supply Chain Optimization Agent
Qdrant client – supplier knowledge base (async wrapper)
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings

logger = logging.getLogger(__name__)

# Embedding dimension assumed for supplier document vectors
VECTOR_DIMENSION: int = 1536


class QdrantSupplierClient:
    """Async Qdrant client for the supplier knowledge base collection."""

    def __init__(self) -> None:
        self._client: Optional[AsyncQdrantClient] = None

    async def connect(self) -> None:
        """Initialise the AsyncQdrantClient and ensure the collection exists."""
        kwargs: Dict[str, Any] = {
            "host": settings.QDRANT_HOST,
            "port": settings.QDRANT_PORT,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        self._client = AsyncQdrantClient(**kwargs)

        # Ensure the supplier_knowledge collection exists
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if settings.QDRANT_COLLECTION not in existing:
            await self._client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=qmodels.VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info(
                "Created Qdrant collection '%s'", settings.QDRANT_COLLECTION
            )
        logger.info(
            "Connected to Qdrant at %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None
        logger.info("Qdrant connection closed")

    def is_connected(self) -> bool:
        return self._client is not None

    # ── document operations ────────────────────────────────────────────────────

    async def upsert_supplier_doc(
        self,
        doc_id: Optional[str],
        vector: List[float],
        payload: Dict[str, Any],
    ) -> str:
        """
        Upsert a supplier knowledge document.

        Parameters
        ----------
        doc_id:  Optional stable UUID string; auto-generated when ``None``.
        vector:  Dense embedding of the document text (length == VECTOR_DIMENSION).
        payload: Metadata dict stored alongside the vector
                 (e.g. supplier_id, document_type, text, source_url).

        Returns the document id.
        """
        point_id = doc_id or str(uuid4())
        await self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.debug("Upserted supplier document id=%s", point_id)
        return point_id

    async def search_supplier_knowledge(
        self,
        query_vector: List[float],
        top_k: int = 5,
        supplier_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over the supplier knowledge collection.

        Parameters
        ----------
        query_vector: Query embedding (length == VECTOR_DIMENSION).
        top_k:        Maximum number of results to return.
        supplier_id:  Optional filter – restrict results to a single supplier.

        Returns a list of dicts with keys: id, score, payload.
        """
        query_filter: Optional[qmodels.Filter] = None
        if supplier_id:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="supplier_id",
                        match=qmodels.MatchValue(value=supplier_id),
                    )
                ]
            )

        results = await self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        hits: List[Dict[str, Any]] = []
        for hit in results:
            hits.append(
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload or {},
                }
            )
        return hits


qdrant_client = QdrantSupplierClient()
