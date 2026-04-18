import os
import json
import asyncio
import jwt
import httpx
from datetime import timezone, datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:5173,http://localhost:8080").split(",")


# ── Auth helper ───────────────────────────────────────────────────────────────
def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


# ── Connection manager (in-process registry, Redis handles cross-instance) ────
class ConnectionManager:
    def __init__(self):
        # room_id -> list of (websocket, user_id)
        self.rooms: dict[str, list[tuple[WebSocket, str]]] = {}

    async def connect(self, room_id: str, ws: WebSocket, user_id: str):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append((ws, user_id))

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.rooms:
            self.rooms[room_id] = [(w, uid) for w, uid in self.rooms[room_id] if w is not ws]

    async def deliver(self, room_id: str, message: dict, exclude: Optional[WebSocket] = None):
        """Send message to all sockets in room (called by Redis subscriber)."""
        dead = []
        for ws, _ in list(self.rooms.get(room_id, [])):
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    def room_users(self, room_id: str) -> list[str]:
        return [uid for _, uid in self.rooms.get(room_id, [])]


manager = ConnectionManager()

# In-memory message history per room (last 50 messages)
history: dict[str, list[dict]] = {}


def add_to_history(room_id: str, msg: dict):
    history.setdefault(room_id, [])
    history[room_id].append(msg)
    history[room_id] = history[room_id][-50:]


# ── Redis Pub/Sub ──────────────────────────────────────────────────────────────
_redis_pool: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


async def publish_to_room(room_id: str, message: dict):
    """Publish a message to the Redis channel for this room.

    The subscriber loop (started on app startup) will pick it up and
    deliver to all connected WebSockets — including those on other
    socket-broker replicas if horizontally scaled.
    """
    redis = get_redis()
    await redis.publish(f"room:{room_id}", json.dumps(message))
    # Also publish to the admin broadcast channel so admin panels see all events.
    await redis.publish("room:admin", json.dumps(message))


async def _redis_subscriber():
    """Background task: subscribe to all room:* channels and deliver messages."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("room:*")
    async for raw in pubsub.listen():
        if raw["type"] != "pmessage":
            continue
        channel: str = raw["channel"]
        try:
            message = json.loads(raw["data"])
        except (json.JSONDecodeError, TypeError):
            continue

        # channel format: "room:<room_id>"
        parts = channel.split(":", 1)
        if len(parts) != 2:
            continue
        room_id = parts[1]

        await manager.deliver(room_id, message)


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="GroupBuy Socket Broker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_redis_subscriber())


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = str(payload.get("sub", "unknown"))
    await manager.connect(room_id, websocket, user_id)

    # Seed history from backend on first access, then send cached history.
    if room_id not in history:
        asyncio.create_task(_load_history_from_backend(room_id, token))
    for msg in history.get(room_id, []):
        await websocket.send_json(msg)

    join_msg = {
        "type": "system",
        "room": room_id,
        "user_id": user_id,
        "text": f"User {user_id} joined",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    add_to_history(room_id, join_msg)
    # Publish via Redis so all replicas and the admin channel see the join event.
    await publish_to_room(room_id, join_msg)

    try:
        while True:
            data = await websocket.receive_json()
            msg = {
                "type": "message",
                "room": room_id,
                "user_id": user_id,
                "text": str(data.get("text", ""))[:2000],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            add_to_history(room_id, msg)
            # Publish via Redis — the subscriber loop delivers to all sockets.
            await publish_to_room(room_id, msg)
            # Persist message in backend asynchronously (fire-and-forget).
            asyncio.create_task(_notify_backend(msg))
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        leave_msg = {
            "type": "system",
            "room": room_id,
            "user_id": user_id,
            "text": f"User {user_id} left",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        add_to_history(room_id, leave_msg)
        await publish_to_room(room_id, leave_msg)


async def _notify_backend(msg: dict):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{BACKEND_URL}/internal/socket-event", json=msg)
    except Exception:
        pass


async def _load_history_from_backend(room_id: str, token: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{BACKEND_URL}/chat/{room_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code == 200:
            for m in r.json():
                add_to_history(room_id, {
                    "type": m.get("msg_type", "message"),
                    "room": room_id,
                    "user_id": str(m.get("user_id", "")) if m.get("user_id") else "system",
                    "text": m.get("text", ""),
                    "timestamp": m.get("timestamp", ""),
                })
    except Exception:
        pass


# ── REST helpers ──────────────────────────────────────────────────────────────
@app.get("/rooms/{room_id}/history")
def get_history(room_id: str):
    return history.get(room_id, [])


@app.get("/rooms/{room_id}/users")
def get_users(room_id: str):
    return manager.room_users(room_id)


@app.get("/health")
def health():
    return {"status": "ok", "rooms": len(manager.rooms)}
