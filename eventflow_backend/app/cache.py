import json
from typing import Any

from redis.asyncio import Redis


class RedisEventCache:
    def __init__(self, redis: Redis, ttl: int) -> None:
        self.redis = redis
        self.ttl = ttl
        self.key = "eventflow:events:list"

    async def get_events(self) -> list[dict[str, Any]] | None:
        cached = await self.redis.get(self.key)
        if cached is None:
            return None
        return json.loads(cached)

    async def set_events(self, events: list[dict[str, Any]]) -> None:
        await self.redis.set(self.key, json.dumps(events), ex=self.ttl)

    async def invalidate(self) -> None:
        await self.redis.delete(self.key)
