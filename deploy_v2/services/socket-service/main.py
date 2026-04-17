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
from contextlib import asynccontextmanager

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ── Auth helper ───────────────────────────────────────────────────────────────
def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


# ── Connection manager ────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[tuple[WebSocket, str]]] = {}
        self.user_sockets: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket, user_id: str):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append((ws, user_id))
        self.user_sockets.setdefault(user_id, []).append(ws)

    def disconnect(self, room_id: str, ws: WebSocket, user_id: str):
        if room_id in self.rooms:
            self.rooms[room_id] = [(w, uid) for w, uid in self.rooms[room_id] if w is not ws]
        if user_id in self.user_sockets:
            self.user_sockets[user_id] = [w for w in self.user_sockets[user_id] if w is not ws]

    async def broadcast(self, room_id: str, message: dict, exclude: Optional[WebSocket] = None):
        for ws, _ in list(self.rooms.get(room_id, [])):
            if ws is not exclude:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def send_to_user(self, user_id: str, message: dict):
        for ws in list(self.user_sockets.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def room_users(self, room_id: str) -> list[str]:
        return [uid for _, uid in self.rooms.get(room_id, [])]


manager = ConnectionManager()

# In-memory message history per room (last 50)
history: dict[str, list[dict]] = {}


def add_to_history(room_id: str, msg: dict):
    history.setdefault(room_id, [])
    history[room_id].append(msg)
    history[room_id] = history[room_id][-50:]


# ── Redis Pub/Sub listener ───────────────────────────────────────────────────
async def redis_listener():
    """Subscribe to Redis channels and relay messages to WebSocket clients.

    Channels:
      room:<room_id>  — broadcast to all clients in that room
      room:admin       — broadcast to all admin-connected sockets
      room:user_<id>   — send to a specific user's sockets
    """
    redis_sub = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_sub.pubsub()
    await pubsub.psubscribe("room:*")

    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] not in ("pmessage",):
                continue
            channel = raw_message["channel"]
            try:
                data = json.loads(raw_message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            if channel.startswith("room:user_"):
                user_id = channel.split("room:user_", 1)[1]
                await manager.send_to_user(user_id, data)
            else:
                room_id = channel.split("room:", 1)[1]
                await manager.broadcast(room_id, data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.punsubscribe("room:*")
        await redis_sub.aclose()


# ── App lifecycle ─────────────────────────────────────────────────────────────
redis_publish_client: Optional[aioredis.Redis] = None
listener_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global redis_publish_client, listener_task
    redis_publish_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    listener_task = asyncio.create_task(redis_listener())
    yield
    if listener_task:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
    if redis_publish_client:
        await redis_publish_client.aclose()


app = FastAPI(title="GroupBuy Socket Service", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    # Send in-memory history; also try to seed from backend on first connect
    if room_id not in history:
        asyncio.create_task(_load_history_from_backend(room_id, token))

    for msg in history.get(room_id, []):
        await websocket.send_json(msg)

    # Notify room of join
    join_msg = {
        "type": "system",
        "room": room_id,
        "user_id": user_id,
        "text": f"User {user_id} joined",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(room_id, join_msg)
    add_to_history(room_id, join_msg)

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
            await manager.broadcast(room_id, msg)

            # Notify backend asynchronously (fire-and-forget)
            asyncio.create_task(_notify_backend(msg))
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket, user_id)
        leave_msg = {
            "type": "system",
            "room": room_id,
            "user_id": user_id,
            "text": f"User {user_id} left",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast(room_id, leave_msg)
        add_to_history(room_id, leave_msg)


async def _notify_backend(msg: dict):
    """Notify backend about a new message (best-effort)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{BACKEND_URL}/internal/socket-event", json=msg)
    except Exception:
        pass


async def _load_history_from_backend(room_id: str, token: str):
    """Seed in-memory history from backend on first room access (best-effort)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{BACKEND_URL}/chat/{room_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code == 200:
            msgs = r.json()
            for m in msgs:
                backend_msg = {
                    "type": m.get("msg_type", "message"),
                    "room": room_id,
                    "user_id": str(m.get("user_id", "")) if m.get("user_id") else "system",
                    "text": m.get("text", ""),
                    "timestamp": m.get("timestamp", ""),
                }
                add_to_history(room_id, backend_msg)
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
