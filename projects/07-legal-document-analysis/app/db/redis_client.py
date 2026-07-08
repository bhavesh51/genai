"""
Project 7 – Legal Document Analysis & Contract Intelligence
Redis async client for session caching and document analysis cache
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClientWrapper:
    """Async Redis wrapper for document analysis caching."""

    def __init__(self) -> None:
        self._pool: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        self._pool = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._pool.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)

    async def close(self) -> None:
        if self._pool:
            await self._pool.aclose()
            logger.info("Redis connection closed")

    def is_connected(self) -> bool:
        return self._pool is not None

    # ── Generic helpers ────────────────────────────────────────────────────

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self._pool.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        await self._pool.set(key, json.dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._pool.delete(key)

    # ── Document analysis cache ────────────────────────────────────────────

    async def get_document(self, doc_id: str) -> Optional[dict]:
        """Retrieve cached document analysis result."""
        return await self.get_json(f"doc:analysis:{doc_id}")

    async def set_document(self, doc_id: str, analysis: dict) -> None:
        """Cache document analysis result for REDIS_DOC_TTL seconds."""
        await self.set_json(f"doc:analysis:{doc_id}", analysis, ttl=settings.REDIS_DOC_TTL)

    async def get_document_clauses(self, doc_id: str) -> Optional[list]:
        """Retrieve cached clause list for a document."""
        return await self.get_json(f"doc:clauses:{doc_id}")

    async def set_document_clauses(self, doc_id: str, clauses: list) -> None:
        """Cache clause list for a document."""
        await self.set_json(f"doc:clauses:{doc_id}", clauses, ttl=settings.REDIS_DOC_TTL)

    # ── Q&A session cache ──────────────────────────────────────────────────

    async def get_qa_result(self, cache_key: str) -> Optional[dict]:
        """Retrieve cached Q&A answer."""
        return await self.get_json(f"qa:{cache_key}")

    async def set_qa_result(self, cache_key: str, result: dict, ttl: int = 600) -> None:
        """Cache Q&A answer for ttl seconds (default 10 min)."""
        await self.set_json(f"qa:{cache_key}", result, ttl=ttl)


redis_client = RedisClientWrapper()
