import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis


class RedisEventCache:
    """Redis cache for event listing responses."""

    def __init__(self, redis: Redis, ttl: int) -> None:
        self.redis = redis
        self.ttl = ttl
        self.prefix = "eventflow:events:list"

    def build_key(
        self,
        page: int,
        size: int,
        date_from: datetime | None,
    ) -> str:
        """Build a cache key that includes pagination and filters."""

        date_marker = date_from.isoformat() if date_from is not None else "any"
        return f"{self.prefix}:{page}:{size}:{date_marker}"

    async def get_events(self, key: str) -> list[dict[str, Any]] | None:
        """Read cached event data by key."""

        cached = await self.redis.get(key)
        if cached is None:
            return None
        return json.loads(cached)

    async def set_events(self, key: str, events: list[dict[str, Any]]) -> None:
        """Store serialized event data under a cache key."""

        await self.redis.set(key, json.dumps(events), ex=self.ttl)

    async def invalidate(self) -> None:
        """Delete all event listing cache entries."""

        async for key in self.redis.scan_iter(match=f"{self.prefix}:*"):
            await self.redis.delete(key)
