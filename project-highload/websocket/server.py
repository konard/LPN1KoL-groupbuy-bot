import asyncio
import json
import logging
import os
import signal
import weakref

import aiohttp
from aiohttp import web
import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SERVER_ID = os.getenv("SERVER_ID", "ws-1")
PORT = int(os.getenv("PORT", "8001"))

# All active WebSocket connections on this instance
_connections: weakref.WeakSet = weakref.WeakSet()


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    _connections.add(ws)
    logger.info("Client connected. Total: %d", len(_connections))

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                pass  # clients are receive-only in this demo
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                break
    finally:
        _connections.discard(ws)
        logger.info("Client disconnected. Total: %d", len(_connections))

    return ws


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "server_id": SERVER_ID, "connections": len(_connections)})


async def broadcast(message: str) -> None:
    if not _connections:
        return
    dead = []
    for ws in list(_connections):
        try:
            await ws.send_str(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.discard(ws)


async def redis_subscriber(app: web.Application) -> None:
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("items:new")
    logger.info("Subscribed to Redis channel items:new (server=%s)", SERVER_ID)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                logger.info("Broadcasting: %s", data)
                await broadcast(json.dumps({"event": "items:new", "data": json.loads(data), "server": SERVER_ID}))
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("items:new")
        await r.aclose()
        logger.info("Redis subscriber shut down")


async def start_subscriber(app: web.Application) -> None:
    app["subscriber"] = asyncio.create_task(redis_subscriber(app))


async def stop_subscriber(app: web.Application) -> None:
    task = app.get("subscriber")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Gracefully close all WebSocket connections
    close_tasks = [ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message=b"Server shutting down")
                   for ws in list(_connections)]
    if close_tasks:
        await asyncio.gather(*close_tasks, return_exceptions=True)
    logger.info("All WebSocket connections closed")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/health", health_handler)
    app.on_startup.append(start_subscriber)
    app.on_cleanup.append(stop_subscriber)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
