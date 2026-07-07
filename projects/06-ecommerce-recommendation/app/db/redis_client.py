"""
Project 6 – E-commerce Product Recommendation Engine
Redis async client for session caching and feature store
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClientWrapper:
    """Async Redis wrapper for feature caching."""

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

    # ── User feature store ─────────────────────────────────────────────────

    async def get_user_features(self, user_id: str) -> Optional[dict]:
        return await self.get_json(f"user:features:{user_id}")

    async def set_user_features(self, user_id: str, features: dict) -> None:
        await self.set_json(f"user:features:{user_id}", features, ttl=settings.REDIS_USER_TTL)

    # ── Product feature store ──────────────────────────────────────────────

    async def get_product_features(self, product_id: str) -> Optional[dict]:
        return await self.get_json(f"product:features:{product_id}")

    async def set_product_features(self, product_id: str, features: dict) -> None:
        await self.set_json(f"product:features:{product_id}", features, ttl=settings.REDIS_PRODUCT_TTL)

    # ── Recommendation cache ───────────────────────────────────────────────

    async def get_recommendations(self, cache_key: str) -> Optional[list]:
        return await self.get_json(f"rec:{cache_key}")

    async def set_recommendations(self, cache_key: str, recs: list, ttl: int = 300) -> None:
        await self.set_json(f"rec:{cache_key}", recs, ttl=ttl)


redis_client = RedisClientWrapper()
