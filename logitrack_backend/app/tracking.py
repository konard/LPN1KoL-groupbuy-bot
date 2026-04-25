import asyncio
import json
from collections import defaultdict
from typing import Any

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import CoordinateHistory, Order, OrderHistory


logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Registry of WebSocket subscribers by order id."""

    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, order_id: int, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""

        await websocket.accept()
        self.connections[order_id].add(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from an order room."""

        self.connections[order_id].discard(websocket)

    async def broadcast(self, order_id: int, payload: dict[str, Any]) -> None:
        """Send a tracking payload to all subscribers."""

        for websocket in list(self.connections[order_id]):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                self.disconnect(order_id, websocket)


def coordinates_key(order_id: int) -> str:
    """Return the Redis key for latest order coordinates."""

    return f"logitrack:orders:{order_id}:coordinates"


def build_geojson_feature(
    order_id: int,
    lat: float,
    lng: float,
    sequence: int,
) -> dict[str, Any]:
    """Build a GeoJSON feature for a courier coordinate."""

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"order_id": order_id, "sequence": sequence},
    }


async def set_latest_coordinates(
    redis: Redis,
    order_id: int,
    payload: dict[str, Any],
) -> None:
    """Store the latest coordinate payload in Redis."""

    await redis.set(coordinates_key(order_id), json.dumps(payload))


async def get_latest_coordinates(redis: Redis, order_id: int) -> dict[str, Any] | None:
    """Read the latest coordinate payload from Redis."""

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
    """Simulate courier movement and handle graceful shutdown cancellation."""

    try:
        for sequence in range(1, 11):
            lat = round(55.751244 + sequence * 0.0012, 6)
            lng = round(37.618423 + sequence * 0.0015, 6)
            payload = build_geojson_feature(order_id, lat, lng, sequence)
            await set_latest_coordinates(redis, order_id, payload)
            await _persist_coordinate(session_factory, order_id, lat, lng, sequence)
            await manager.broadcast(order_id, payload)
            await asyncio.sleep(2)

        await _mark_order_status(session_factory, order_id, "delivered")
    except asyncio.CancelledError:
        await _mark_order_status(session_factory, order_id, "tracking_cancelled")
        logger.info("tracking_cancelled", order_id=order_id)
        raise


async def _persist_coordinate(
    session_factory: async_sessionmaker[AsyncSession],
    order_id: int,
    lat: float,
    lng: float,
    sequence: int,
) -> None:
    async with session_factory() as session:
        session.add(
            CoordinateHistory(
                order_id=order_id,
                lat=lat,
                lng=lng,
                sequence=sequence,
            )
        )
        await session.commit()


async def _mark_order_status(
    session_factory: async_sessionmaker[AsyncSession],
    order_id: int,
    status: str,
) -> None:
    async with session_factory() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.status = status
            session.add(OrderHistory(order_id=order_id, status=status))
            await session.commit()
