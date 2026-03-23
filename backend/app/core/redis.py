"""Async Redis client singleton for session and cache storage."""
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    """Return a lazy-initialized async Redis client.

    Uses settings.REDIS_URL (default: redis://localhost:6379/0).
    Connection is reused across calls (singleton pattern).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _redis_client
