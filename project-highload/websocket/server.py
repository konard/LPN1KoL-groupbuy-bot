import asyncio
import json
import logging
import os
import socket
from typing import Any

from aiohttp import WSCloseCode, WSMsgType, web
from redis.asyncio import Redis


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("groupbuy.websocket")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_CHANNEL = os.getenv("REDIS_CHANNEL", "items:new")
SERVER_ID = os.getenv("SERVER_ID", socket.gethostname())
HEARTBEAT_SECONDS = int(os.getenv("WS_HEARTBEAT_SECONDS", "25"))


class WebSocketServer:
    def __init__(self) -> None:
        self.app = web.Application()
        self.connections: set[web.WebSocketResponse] = set()
        self.redis: Redis | None = None
        self.pubsub = None
        self.listener_task: asyncio.Task | None = None
        self.redis_ready = False
        self.stopping = False
        self.broadcast_total = 0
        self.connection_total = 0

        self.app.router.add_get("/healthz", self.healthz)
        self.app.router.add_get("/readyz", self.readyz)
        self.app.router.add_get("/metrics", self.metrics)
        self.app.router.add_get("/ws/items", self.websocket_handler)
        self.app.router.add_get("/ws/", self.websocket_handler)
        self.app.on_startup.append(self.on_startup)
        self.app.on_shutdown.append(self.on_shutdown)

    async def healthz(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "server_id": SERVER_ID})

    async def readyz(self, request: web.Request) -> web.Response:
        if not self.redis_ready:
            return web.json_response(
                {"status": "not_ready", "redis": "disconnected"},
                status=503,
            )
        return web.json_response({"status": "ready", "redis": "connected"})

    async def metrics(self, request: web.Request) -> web.Response:
        body = "\n".join(
            [
                "# HELP groupbuy_websocket_connections Active WebSocket connections",
                "# TYPE groupbuy_websocket_connections gauge",
                f"groupbuy_websocket_connections {len(self.connections)}",
                "# HELP groupbuy_websocket_broadcast_total Redis events broadcast locally",
                "# TYPE groupbuy_websocket_broadcast_total counter",
                f"groupbuy_websocket_broadcast_total {self.broadcast_total}",
                "# HELP groupbuy_websocket_connection_total Connections accepted by this instance",
                "# TYPE groupbuy_websocket_connection_total counter",
                f"groupbuy_websocket_connection_total {self.connection_total}",
                "",
            ]
        )
        return web.Response(text=body, content_type="text/plain")

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=HEARTBEAT_SECONDS)
        await ws.prepare(request)

        self.connections.add(ws)
        self.connection_total += 1
        await ws.send_json({"type": "connected", "server_id": SERVER_ID})

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self.handle_client_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.warning("websocket error: %s", ws.exception())
        finally:
            self.connections.discard(ws)

        return ws

    async def handle_client_message(self, ws: web.WebSocketResponse, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"type": "message", "text": raw}

        if payload.get("type") == "ping":
            await ws.send_json({"type": "pong", "server_id": SERVER_ID})

    async def on_startup(self, app: web.Application) -> None:
        self.listener_task = asyncio.create_task(self.redis_listener())

    async def on_shutdown(self, app: web.Application) -> None:
        self.stopping = True
        if self.listener_task is not None:
            self.listener_task.cancel()
            await asyncio.gather(self.listener_task, return_exceptions=True)

        if self.pubsub is not None:
            await self.pubsub.close()
        if self.redis is not None:
            await self.redis.aclose()

        close_tasks = [
            ws.close(code=WSCloseCode.GOING_AWAY, message=b"server shutdown")
            for ws in list(self.connections)
            if not ws.closed
        ]
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

    async def redis_listener(self) -> None:
        delay = 1.0
        while not self.stopping:
            try:
                self.redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self.redis.ping()
                self.pubsub = self.redis.pubsub()
                await self.pubsub.subscribe(REDIS_CHANNEL)
                self.redis_ready = True
                delay = 1.0
                logger.info("subscribed to Redis Pub/Sub channel %s", REDIS_CHANNEL)

                async for message in self.pubsub.listen():
                    if self.stopping:
                        break
                    if message.get("type") != "message":
                        continue
                    await self.broadcast(self.parse_message(message.get("data")))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis Pub/Sub listener failed; reconnecting")
                self.redis_ready = False
                await self.close_redis()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15.0)

    def parse_message(self, data: Any) -> dict[str, Any]:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        try:
            return json.loads(data)
        except (TypeError, json.JSONDecodeError):
            return {"type": "message", "data": data}

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.connections:
            return

        payload = {**payload, "server_id": SERVER_ID}
        encoded = json.dumps(payload, ensure_ascii=True)
        send_tasks = [
            ws.send_str(encoded)
            for ws in list(self.connections)
            if not ws.closed
        ]
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
            self.broadcast_total += 1

    async def close_redis(self) -> None:
        if self.pubsub is not None:
            await self.pubsub.close()
            self.pubsub = None
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None


def create_app() -> web.Application:
    return WebSocketServer().app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8001, shutdown_timeout=10)
