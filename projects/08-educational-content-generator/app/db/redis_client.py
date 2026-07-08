"""
Project 8 – Educational Content Generator
Redis client for sessions, quizzes, and mastery state
"""
import json
import logging
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCacheClient:
    def __init__(self):
        self._client: Redis | None = None

    async def connect(self):
        self._client = Redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("Connected to Redis")

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def is_connected(self) -> bool:
        return self._client is not None

    async def set_json(self, key: str, value: Any, ttl: int):
        client = self._require_client()
        await client.set(key, json.dumps(value), ex=ttl)

    async def get_json(self, key: str) -> Any:
        client = self._require_client()
        value = await client.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def delete(self, key: str):
        client = self._require_client()
        await client.delete(key)

    async def get_topic_mastery(self, learner_id: str, topic: str) -> float | None:
        data = await self.get_json(f"mastery:{learner_id}")
        if not data:
            return None
        return data.get(topic)

    async def set_topic_mastery(self, learner_id: str, topic: str, mastery: float):
        key = f"mastery:{learner_id}"
        data = await self.get_json(key) or {}
        data[topic] = mastery
        await self.set_json(key, data, settings.REDIS_MASTERY_TTL)

    async def get_all_mastery(self, learner_id: str) -> dict[str, float]:
        data = await self.get_json(f"mastery:{learner_id}")
        return data or {}

    def _require_client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not connected")
        return self._client


redis_client = RedisCacheClient()
