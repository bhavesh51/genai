"""
Project 10 – Creative Content Generation Platform
Redis async client for asset caching and job status management
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClientWrapper:
    """Async Redis wrapper for creative asset and job status caching."""

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

    # ── Generic helpers ────────────────────────────────────────────────────────

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self._pool.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        await self._pool.set(key, json.dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._pool.delete(key)

    # ── Creative asset cache ───────────────────────────────────────────────────

    async def get_asset(self, asset_id: str) -> Optional[dict]:
        """Retrieve a creative asset payload by asset_id."""
        return await self.get_json(f"asset:{asset_id}")

    async def set_asset(self, asset_id: str, payload: dict) -> None:
        """Store a creative asset with the configured TTL."""
        await self.set_json(f"asset:{asset_id}", payload, ttl=settings.REDIS_ASSET_TTL)

    async def delete_asset(self, asset_id: str) -> None:
        """Remove a creative asset from the cache."""
        await self.delete(f"asset:{asset_id}")

    async def update_asset_field(self, asset_id: str, field: str, value: Any) -> bool:
        """
        Fetch an existing asset, update a single field, and re-persist it.
        Returns True if the asset existed and was updated, False otherwise.
        """
        payload = await self.get_asset(asset_id)
        if payload is None:
            return False
        payload[field] = value
        await self.set_asset(asset_id, payload)
        return True

    # ── Job status cache ───────────────────────────────────────────────────────

    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Retrieve job status dict."""
        return await self.get_json(f"job:{job_id}")

    async def set_job_status(self, job_id: str, status: dict, ttl: int = 3600) -> None:
        """Persist job status with a 1-hour default TTL."""
        await self.set_json(f"job:{job_id}", status, ttl=ttl)


redis_client = RedisClientWrapper()
