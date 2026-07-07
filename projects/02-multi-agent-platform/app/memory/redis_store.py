"""
Project 2 – Multi-Agent Platform
Redis-backed shared agent memory store
"""
import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisMemoryStore:
    """Async Redis client for agent state persistence."""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await self._client.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)

    async def close(self):
        if self._client:
            await self._client.close()
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None

    async def save_state(self, session_id: str, state: Dict[str, Any]) -> None:
        key = f"agent:state:{session_id}"
        await self._client.setex(key, settings.REDIS_TTL_SECONDS, json.dumps(state))

    async def load_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = f"agent:state:{session_id}"
        data = await self._client.get(key)
        return json.loads(data) if data else None

    async def append_message(self, session_id: str, message: Dict[str, Any]) -> None:
        key = f"agent:history:{session_id}"
        await self._client.rpush(key, json.dumps(message))
        await self._client.expire(key, settings.REDIS_TTL_SECONDS)

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        key = f"agent:history:{session_id}"
        raw = await self._client.lrange(key, 0, -1)
        return [json.loads(m) for m in raw]

    async def delete_session(self, session_id: str) -> None:
        await self._client.delete(
            f"agent:state:{session_id}",
            f"agent:history:{session_id}",
        )


redis_store = RedisMemoryStore()
