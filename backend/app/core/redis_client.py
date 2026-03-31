"""
KYC Application - Redis Client Module

Provides an async Redis client with connection pooling, helper methods
for common operations (get/set/delete/pub-sub), and dependency injection.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any, Optional, Union

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Redis Client Wrapper
# =============================================================================

class RedisClient:
    """
    Async Redis client wrapper with helper methods.

    Provides a clean interface for common Redis operations with
    error handling, JSON serialization, and connection management.
    """

    def __init__(self):
        self._client: Optional[Redis] = None
        self._pool: Optional[ConnectionPool] = None

    def _get_client(self) -> Redis:
        """Get or create the Redis client."""
        if self._client is None:
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            self._client = Redis(connection_pool=self._pool)
        return self._client

    @property
    def client(self) -> Redis:
        """Access the underlying Redis client."""
        return self._get_client()

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            result = await self._get_client().ping()
            return result is True
        except RedisError as e:
            logger.error("Redis ping failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    # -------------------------------------------------------------------------
    # String Operations
    # -------------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """Get a string value by key."""
        try:
            return await self._get_client().get(key)
        except RedisError as e:
            logger.error("Redis GET failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Set a string value.

        Args:
            key: Redis key
            value: String value to store
            ttl: Time-to-live in seconds (None = no expiry)
            nx: Only set if key does NOT exist
            xx: Only set if key DOES exist
        """
        try:
            kwargs: dict[str, Any] = {}
            if ttl is not None:
                kwargs["ex"] = ttl
            if nx:
                kwargs["nx"] = True
            if xx:
                kwargs["xx"] = True
            result = await self._get_client().set(key, value, **kwargs)
            return result is not None
        except RedisError as e:
            logger.error("Redis SET failed", key=key, error=str(e))
            return False

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns count of deleted keys."""
        try:
            return await self._get_client().delete(*keys)
        except RedisError as e:
            logger.error("Redis DELETE failed", keys=keys, error=str(e))
            return 0

    async def exists(self, *keys: str) -> int:
        """Check if one or more keys exist. Returns count of existing keys."""
        try:
            return await self._get_client().exists(*keys)
        except RedisError as e:
            logger.error("Redis EXISTS failed", error=str(e))
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiry on a key. Returns True if key exists."""
        try:
            return await self._get_client().expire(key, ttl)
        except RedisError as e:
            logger.error("Redis EXPIRE failed", key=key, error=str(e))
            return False

    async def ttl(self, key: str) -> int:
        """Get TTL of a key. Returns -1 if no TTL, -2 if key doesn't exist."""
        try:
            return await self._get_client().ttl(key)
        except RedisError as e:
            logger.error("Redis TTL failed", key=key, error=str(e))
            return -2

    # -------------------------------------------------------------------------
    # JSON Operations
    # -------------------------------------------------------------------------

    async def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize a JSON value."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Redis JSON decode failed", key=key, error=str(e))
            return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        """Serialize and store a JSON value."""
        try:
            serialized = json.dumps(value, default=str)
            return await self.set(key, serialized, ttl=ttl, nx=nx)
        except (TypeError, ValueError) as e:
            logger.error("Redis JSON encode failed", key=key, error=str(e))
            return False

    # -------------------------------------------------------------------------
    # Counter Operations
    # -------------------------------------------------------------------------

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter by amount."""
        try:
            return await self._get_client().incr(key, amount)
        except RedisError as e:
            logger.error("Redis INCR failed", key=key, error=str(e))
            return None

    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a counter by amount."""
        try:
            return await self._get_client().decr(key, amount)
        except RedisError as e:
            logger.error("Redis DECR failed", key=key, error=str(e))
            return None

    # -------------------------------------------------------------------------
    # Hash Operations
    # -------------------------------------------------------------------------

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get a hash field value."""
        try:
            return await self._get_client().hget(name, key)
        except RedisError as e:
            logger.error("Redis HGET failed", name=name, key=key, error=str(e))
            return None

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        """Set multiple hash fields."""
        try:
            return await self._get_client().hset(name, mapping=mapping)
        except RedisError as e:
            logger.error("Redis HSET failed", name=name, error=str(e))
            return 0

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all fields and values of a hash."""
        try:
            return await self._get_client().hgetall(name)
        except RedisError as e:
            logger.error("Redis HGETALL failed", name=name, error=str(e))
            return {}

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        try:
            return await self._get_client().hdel(name, *keys)
        except RedisError as e:
            logger.error("Redis HDEL failed", name=name, error=str(e))
            return 0

    # -------------------------------------------------------------------------
    # List Operations
    # -------------------------------------------------------------------------

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the left of a list."""
        try:
            return await self._get_client().lpush(key, *values)
        except RedisError as e:
            logger.error("Redis LPUSH failed", key=key, error=str(e))
            return 0

    async def rpop(self, key: str) -> Optional[str]:
        """Pop a value from the right of a list."""
        try:
            return await self._get_client().rpop(key)
        except RedisError as e:
            logger.error("Redis RPOP failed", key=key, error=str(e))
            return None

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """Get a range of list elements."""
        try:
            return await self._get_client().lrange(key, start, end)
        except RedisError as e:
            logger.error("Redis LRANGE failed", key=key, error=str(e))
            return []

    # -------------------------------------------------------------------------
    # Set Operations
    # -------------------------------------------------------------------------

    async def sadd(self, key: str, *members: str) -> int:
        """Add members to a set."""
        try:
            return await self._get_client().sadd(key, *members)
        except RedisError as e:
            logger.error("Redis SADD failed", key=key, error=str(e))
            return 0

    async def sismember(self, key: str, member: str) -> bool:
        """Check if a member exists in a set."""
        try:
            return await self._get_client().sismember(key, member)
        except RedisError as e:
            logger.error("Redis SISMEMBER failed", key=key, error=str(e))
            return False

    async def srem(self, key: str, *members: str) -> int:
        """Remove members from a set."""
        try:
            return await self._get_client().srem(key, *members)
        except RedisError as e:
            logger.error("Redis SREM failed", key=key, error=str(e))
            return 0

    # -------------------------------------------------------------------------
    # Rate Limiting Helper
    # -------------------------------------------------------------------------

    async def rate_limit_check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check if a rate limit has been exceeded using sliding window.

        Args:
            key: Rate limit key (e.g., f"rate:{user_id}:{endpoint}")
            max_requests: Maximum allowed requests per window
            window_seconds: Window duration in seconds

        Returns:
            Tuple of (is_allowed: bool, current_count: int)
        """
        try:
            pipe = self._get_client().pipeline()
            await pipe.incr(key)
            await pipe.expire(key, window_seconds)
            results = await pipe.execute()
            current_count = results[0]
            return current_count <= max_requests, current_count
        except RedisError as e:
            logger.error("Rate limit check failed", key=key, error=str(e))
            # Fail open: allow the request if Redis is unavailable
            return True, 0

    # -------------------------------------------------------------------------
    # Session / Token Management
    # -------------------------------------------------------------------------

    async def store_token(
        self,
        token_key: str,
        user_id: str,
        ttl: int,
    ) -> bool:
        """Store a JWT token with user ID for validation."""
        return await self.set(
            f"token:{token_key}",
            user_id,
            ttl=ttl,
        )

    async def get_token_user(self, token_key: str) -> Optional[str]:
        """Get user ID associated with a token."""
        return await self.get(f"token:{token_key}")

    async def revoke_token(self, token_key: str) -> bool:
        """Revoke a token by deleting it from Redis."""
        deleted = await self.delete(f"token:{token_key}")
        return deleted > 0

    async def is_token_revoked(self, token_key: str) -> bool:
        """Check if a token has been revoked (added to blocklist)."""
        return await self.sismember("revoked_tokens", token_key)

    async def add_to_blocklist(self, token_key: str, ttl: int) -> None:
        """Add a token to the revocation blocklist."""
        await self.sadd("revoked_tokens", token_key)
        # Note: The set itself doesn't expire; individual entries aren't cleaned up
        # In production, use a sorted set with scores as expiry timestamps


# =============================================================================
# Global Redis Client Instance
# =============================================================================

redis_client = RedisClient()


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """
    FastAPI dependency that provides the Redis client.

    Usage:
        @router.get("/items")
        async def get_items(redis: RedisClient = Depends(get_redis)):
            value = await redis.get("some_key")
    """
    yield redis_client
