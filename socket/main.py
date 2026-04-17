import os
import jwt
import asyncio
import httpx
from datetime import timezone, datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")


# ── Auth helper ───────────────────────────────────────────────────────────────
def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


# ── Connection manager ────────────────────────────────────────────────────────
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

    async def broadcast(self, room_id: str, message: dict, exclude: Optional[WebSocket] = None):
        for ws, _ in list(self.rooms.get(room_id, [])):
            if ws is not exclude:
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


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="GroupBuy Socket Service", version="1.0.0")

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
        manager.disconnect(room_id, websocket)
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
