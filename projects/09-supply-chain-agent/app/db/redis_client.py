"""
Project 9 – Supply Chain Optimization Agent
Redis client – async agent state cache with JSON serialisation
"""
import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for agent session state persistence."""

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        self._client = await aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await self._client.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None
        logger.info("Redis connection closed")

    def is_connected(self) -> bool:
        return self._client is not None

    # ── generic JSON helpers ───────────────────────────────────────────────────

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Serialise *value* to JSON and store with optional TTL (seconds)."""
        ttl = ttl if ttl is not None else settings.REDIS_SESSION_TTL
        await self._client.setex(key, ttl, json.dumps(value))

    async def get_json(self, key: str) -> Optional[Any]:
        """Return the JSON-deserialised value for *key*, or ``None``."""
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    # ── agent state cache ──────────────────────────────────────────────────────

    async def save_agent_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Persist agent state keyed by session_id."""
        key = f"supply:agent:state:{session_id}"
        await self.set_json(key, state)
        logger.debug("Saved agent state for session %s", session_id)

    async def load_agent_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent state for *session_id*."""
        key = f"supply:agent:state:{session_id}"
        return await self.get_json(key)

    async def delete_agent_state(self, session_id: str) -> None:
        """Remove all keys associated with *session_id*."""
        await self._client.delete(
            f"supply:agent:state:{session_id}",
            f"supply:agent:history:{session_id}",
        )

    async def append_history(self, session_id: str, message: Dict[str, Any]) -> None:
        """Append a message dict to the session history list."""
        key = f"supply:agent:history:{session_id}"
        await self._client.rpush(key, json.dumps(message))
        await self._client.expire(key, settings.REDIS_SESSION_TTL)

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Return the full message history for *session_id*."""
        key = f"supply:agent:history:{session_id}"
        raw = await self._client.lrange(key, 0, -1)
        return [json.loads(m) for m in raw]


redis_client = RedisClient()
