"""Redis caching utilities for performance optimization."""
import json
import pickle
from typing import Any, Optional, Callable
from functools import wraps
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Manager for Redis caching operations."""

    def __init__(self):
        """Initialize cache manager."""
        self._redis: Optional[Redis] = None

    async def get_redis(self) -> Redis:
        """
        Get or create Redis connection.

        Returns:
            Redis client instance
        """
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            redis_client = await self.get_redis()
            value = await redis_client.get(key)
            if value is None:
                logger.debug(f"Cache miss: {key}")
                return None

            logger.debug(f"Cache hit: {key}")
            return pickle.loads(value)
        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {str(e)}")
            return None

    async def set(
        self, key: str, value: Any, ttl: int = 300
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 300 = 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            serialized = pickle.dumps(value)
            await redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            result = await redis_client.delete(key)
            logger.debug(f"Cache delete: {key}")
            return bool(result)
        except Exception as e:
            logger.warning(f"Cache delete error for key '{key}': {str(e)}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        try:
            redis_client = await self.get_redis()
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await redis_client.delete(*keys)
                logger.debug(f"Cache delete pattern '{pattern}': {deleted} keys")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern error for '{pattern}': {str(e)}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            result = await redis_client.exists(key)
            return bool(result)
        except Exception as e:
            logger.warning(f"Cache exists error for key '{key}': {str(e)}")
            return False


# Global cache manager instance
cache_manager = CacheManager()


def cache_key_builder(*parts: str) -> str:
    """
    Build a cache key from parts.

    Args:
        *parts: Key parts to join

    Returns:
        Cache key string

    Example:
        >>> cache_key_builder("user", "email", "test@example.com")
        'user:email:test@example.com'
    """
    return ":".join(str(part) for part in parts)


def cached(
    key_prefix: str,
    ttl: int = 300,
    key_builder: Optional[Callable] = None,
):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds (default: 300)
        key_builder: Optional function to build cache key from args/kwargs

    Example:
        @cached(key_prefix="user:email", ttl=600)
        async def get_user_by_email(email: str):
            # Function implementation
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use prefix and first argument
                arg_key = args[0] if args else "default"
                cache_key = cache_key_builder(key_prefix, str(arg_key))

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# Cache key TTL constants (in seconds)
CACHE_TTL_USER = 600  # 10 minutes
CACHE_TTL_CLAIM = 300  # 5 minutes
CACHE_TTL_AUDIT_RESULT = 180  # 3 minutes
CACHE_TTL_STATS = 120  # 2 minutes
