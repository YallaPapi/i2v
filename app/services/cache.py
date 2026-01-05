"""Redis caching service for API responses."""

import os
import json
from typing import Optional, Any
from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger()

# Redis client - initialized lazily
_redis_client = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default


async def get_redis():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            import aioredis
            _redis_client = await aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await _redis_client.ping()
            logger.info("Redis connected", url=REDIS_URL)
        except Exception as e:
            logger.warning("Redis not available, caching disabled", error=str(e))
            _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Optional[str]:
    """Get value from cache."""
    redis = await get_redis()
    if redis is None:
        return None
    try:
        return await redis.get(key)
    except Exception as e:
        logger.warning("Cache get failed", key=key, error=str(e))
        return None


async def cache_set(key: str, value: str, ttl: int = CACHE_TTL) -> bool:
    """Set value in cache with TTL."""
    redis = await get_redis()
    if redis is None:
        return False
    try:
        await redis.setex(key, ttl, value)
        return True
    except Exception as e:
        logger.warning("Cache set failed", key=key, error=str(e))
        return False


async def cache_delete(pattern: str) -> int:
    """Delete keys matching pattern."""
    redis = await get_redis()
    if redis is None:
        return 0
    try:
        keys = await redis.keys(pattern)
        if keys:
            return await redis.delete(*keys)
        return 0
    except Exception as e:
        logger.warning("Cache delete failed", pattern=pattern, error=str(e))
        return 0


async def invalidate_pipelines_cache():
    """Invalidate all pipeline list caches."""
    deleted = await cache_delete("pipelines:*")
    if deleted:
        logger.info("Invalidated pipeline caches", count=deleted)


def make_cache_key(prefix: str, **kwargs) -> str:
    """Generate cache key from prefix and kwargs."""
    parts = [prefix]
    for k, v in sorted(kwargs.items()):
        if v is not None:
            parts.append(f"{k}={v}")
    return ":".join(parts)
