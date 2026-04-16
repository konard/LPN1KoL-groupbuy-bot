import json
import os
from typing import Any

from redis.asyncio import Redis


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_CHANNEL = os.getenv("REDIS_CHANNEL", "items:new")


class RedisPublisher:
    def __init__(self) -> None:
        self.client: Redis | None = None

    async def connect(self) -> None:
        self.client = Redis.from_url(REDIS_URL, decode_responses=True)
        await self.client.ping()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def ping(self) -> None:
        if self.client is None:
            await self.connect()
        assert self.client is not None
        await self.client.ping()

    async def publish_item_created(self, item: dict[str, Any]) -> None:
        if self.client is None:
            await self.connect()
        assert self.client is not None
        payload = {"type": "item.created", "item": item}
        await self.client.publish(REDIS_CHANNEL, json.dumps(payload, ensure_ascii=True))


redis_publisher = RedisPublisher()
