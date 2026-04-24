import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import Order, OrderHistory


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, order_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[order_id].add(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket) -> None:
        self.connections[order_id].discard(websocket)

    async def broadcast(self, order_id: int, payload: dict[str, Any]) -> None:
        for websocket in list(self.connections[order_id]):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                self.disconnect(order_id, websocket)


def coordinates_key(order_id: int) -> str:
    return f"logitrack:orders:{order_id}:coordinates"


async def set_latest_coordinates(
    redis: Redis,
    order_id: int,
    payload: dict[str, Any],
) -> None:
    await redis.set(coordinates_key(order_id), json.dumps(payload))


async def get_latest_coordinates(redis: Redis, order_id: int) -> dict[str, Any] | None:
    cached = await redis.get(coordinates_key(order_id))
    if cached is None:
        return None
    return json.loads(cached)


async def simulate_courier(
    order_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    manager: ConnectionManager,
) -> None:
    for sequence in range(1, 11):
        payload = {
            "order_id": order_id,
            "lat": round(55.751244 + sequence * 0.0012, 6),
            "lng": round(37.618423 + sequence * 0.0015, 6),
            "sequence": sequence,
        }
        await set_latest_coordinates(redis, order_id, payload)
        await manager.broadcast(order_id, payload)
        await asyncio.sleep(2)

    async with session_factory() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.status = "delivered"
            session.add(OrderHistory(order_id=order_id, status="delivered"))
            await session.commit()
