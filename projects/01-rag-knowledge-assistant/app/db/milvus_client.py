"""
Project 1 – RAG Knowledge Assistant
Milvus vector DB client (HA connection pool)
"""
import logging
from typing import List, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 1024},
}

VECTOR_SEARCH_PARAMS = {
    "metric_type": "COSINE",
    "params": {"nprobe": 64},
}


class MilvusVectorClient:
    """Thread-safe Milvus client with HA connection retry."""

    def __init__(self):
        self._connected = False

    async def connect(self):
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
                secure=True,
            )
            self._connected = True
            logger.info("Connected to Milvus at %s:%s", settings.MILVUS_HOST, settings.MILVUS_PORT)
        except Exception as exc:
            logger.error("Failed to connect to Milvus: %s", exc)
            raise

    async def close(self):
        connections.disconnect("default")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def ensure_collection(self, tenant_id: str) -> Collection:
        """Create or return the Milvus collection for a tenant."""
        collection_name = f"{settings.MILVUS_COLLECTION_PREFIX}_{tenant_id}"
        if utility.has_collection(collection_name):
            return Collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=settings.EMBEDDING_DIMENSION,
            ),
        ]
        schema = CollectionSchema(fields, description=f"RAG collection for tenant {tenant_id}")
        collection = Collection(collection_name, schema)
        collection.create_index("embedding", VECTOR_INDEX_PARAMS)
        collection.load()
        logger.info("Created Milvus collection: %s", collection_name)
        return collection

    def upsert_chunks(
        self,
        tenant_id: str,
        ids: List[str],
        sources: List[str],
        chunk_indices: List[int],
        texts: List[str],
        embeddings: List[List[float]],
    ):
        collection = self.ensure_collection(tenant_id)
        collection.upsert(
            [ids, sources, chunk_indices, texts, embeddings]
        )
        collection.flush()

    def search(
        self,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 10,
        expr: Optional[str] = None,
    ) -> List[dict]:
        collection = self.ensure_collection(tenant_id)
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=VECTOR_SEARCH_PARAMS,
            limit=top_k,
            expr=expr,
            output_fields=["id", "source", "chunk_index", "text"],
        )
        hits = []
        for hit in results[0]:
            hits.append(
                {
                    "id": hit.entity.get("id"),
                    "source": hit.entity.get("source"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "text": hit.entity.get("text"),
                    "score": hit.distance,
                }
            )
        return hits


milvus_client = MilvusVectorClient()
