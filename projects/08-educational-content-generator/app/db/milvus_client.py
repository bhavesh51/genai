"""
Project 8 – Educational Content Generator
Milvus vector DB client
"""
import logging
from typing import Any, List

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

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
            )
            self.ensure_collection()
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

    def ensure_collection(self) -> Collection:
        if utility.has_collection(settings.MILVUS_COLLECTION):
            collection = Collection(settings.MILVUS_COLLECTION)
            collection.load()
            return collection

        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="subject", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="topic", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIMENSION),
        ]
        schema = CollectionSchema(fields, description="Educational curriculum chunks")
        collection = Collection(settings.MILVUS_COLLECTION, schema)
        collection.create_index("embedding", VECTOR_INDEX_PARAMS)
        collection.load()
        logger.info("Created Milvus collection: %s", settings.MILVUS_COLLECTION)
        return collection

    async def upsert_chunk(self, chunk_id: str, subject: str, topic: str, text: str, embedding: List[float]):
        collection = self.ensure_collection()
        collection.upsert([[chunk_id], [subject], [topic], [text], [embedding]])
        collection.flush()

    async def search_curriculum(
        self,
        embedding: List[float],
        subject: str | None = None,
        topic: str | None = None,
        top_k: int = 5,
    ) -> List[dict[str, Any]]:
        collection = self.ensure_collection()
        filters = []
        if subject:
            filters.append(f'subject == "{subject}"')
        if topic:
            filters.append(f'topic == "{topic}"')
        expr = " and ".join(filters) if filters else None
        results = collection.search(
            data=[embedding],
            anns_field="embedding",
            param=VECTOR_SEARCH_PARAMS,
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "subject", "topic", "text"],
        )
        hits: List[dict[str, Any]] = []
        for hit in results[0]:
            hits.append(
                {
                    "chunk_id": hit.entity.get("chunk_id"),
                    "subject": hit.entity.get("subject"),
                    "topic": hit.entity.get("topic"),
                    "text": hit.entity.get("text"),
                    "score": hit.distance,
                }
            )
        return hits


milvus_client = MilvusVectorClient()
