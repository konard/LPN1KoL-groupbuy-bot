import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chat-service")

PORT = int(os.getenv("PORT", "4004"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/chat_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://centrifugo:8000")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "centrifugo_api_key")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None

MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE room_type AS ENUM ('purchase','direct','group');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE msg_type AS ENUM ('text','system','image','video','file');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS rooms (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    type        room_type NOT NULL DEFAULT 'group',
    purchase_id UUID,
    created_by  UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id    UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (room_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id      UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL,
    content      TEXT NOT NULL DEFAULT '',
    type         msg_type NOT NULL DEFAULT 'text',
    media_url    TEXT,
    is_edited    BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    edit_history JSONB NOT NULL DEFAULT '[]',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS media_library (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uploader_id       UUID NOT NULL,
    filename          TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type         TEXT NOT NULL,
    size              BIGINT NOT NULL,
    url               TEXT NOT NULL,
    sha256            TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_room_members_user ON room_members(user_id);
"""


async def _centrifugo_publish(channel: str, data: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{CENTRIFUGO_URL}/api/publish",
                headers={"X-API-Key": CENTRIFUGO_API_KEY, "Content-Type": "application/json"},
                json={"channel": channel, "data": data},
            )
    except Exception as exc:
        logger.warning("Centrifugo publish failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _redis
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Chat service started on :%d", PORT)
    yield
    await _pool.close()
    await _redis.aclose()
    logger.info("Chat service stopped")


app = FastAPI(title="Chat Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pool() -> asyncpg.Pool:
    return _pool


def get_redis() -> aioredis.Redis:
    return _redis


def _user_id(x_user_id: Optional[str] = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateRoomRequest(BaseModel):
    name: str
    type: str = "group"
    purchaseId: str | None = None
    memberIds: list[str] = []


class SendMessageRequest(BaseModel):
    content: str
    type: str = "text"
    mediaUrl: str | None = None


class EditMessageRequest(BaseModel):
    content: str


# ─── Rooms ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "chat-service"}


@app.post("/rooms", status_code=201)
async def create_room(
    body: CreateRoomRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        async with conn.transaction():
            room_id = await conn.fetchval(
                "INSERT INTO rooms(name, type, purchase_id, created_by) VALUES($1,$2,$3,$4) RETURNING id",
                body.name, body.type,
                uuid.UUID(body.purchaseId) if body.purchaseId else None,
                uuid.UUID(user_id),
            )
            member_ids = list({user_id} | set(body.memberIds))
            await conn.executemany(
                "INSERT INTO room_members(room_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
                [(room_id, uuid.UUID(mid)) for mid in member_ids],
            )
    return {"success": True, "roomId": str(room_id)}


@app.get("/rooms")
async def list_rooms(user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        """SELECT r.id, r.name, r.type, r.purchase_id, r.is_archived, r.created_at
           FROM rooms r
           JOIN room_members rm ON rm.room_id = r.id
           WHERE rm.user_id = $1
           ORDER BY r.updated_at DESC""",
        uuid.UUID(user_id),
    )
    return {"success": True, "data": [
        dict(r) | {"id": str(r["id"]), "purchaseId": str(r["purchase_id"]) if r["purchase_id"] else None}
        for r in rows
    ]}


@app.post("/rooms/{room_id}/members/{member_id}")
async def add_member(room_id: str, member_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    await pool.execute(
        "INSERT INTO room_members(room_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
        uuid.UUID(room_id), uuid.UUID(member_id),
    )
    return {"success": True}


# ─── Messages ─────────────────────────────────────────────────────────────────

@app.get("/rooms/{room_id}/messages")
async def list_messages(
    room_id: str,
    limit: int = 50,
    before: str | None = None,
    pool: asyncpg.Pool = Depends(get_pool),
):
    if before:
        rows = await pool.fetch(
            "SELECT * FROM messages WHERE room_id=$1 AND created_at < $2 AND NOT is_deleted ORDER BY created_at DESC LIMIT $3",
            uuid.UUID(room_id), datetime.fromisoformat(before), limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM messages WHERE room_id=$1 AND NOT is_deleted ORDER BY created_at DESC LIMIT $2",
            uuid.UUID(room_id), limit,
        )
    return {"success": True, "data": [
        dict(r) | {"id": str(r["id"]), "roomId": str(r["room_id"]), "userId": str(r["user_id"])}
        for r in reversed(rows)
    ]}


@app.post("/rooms/{room_id}/messages", status_code=201)
async def send_message(
    room_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    msg_id = await pool.fetchval(
        "INSERT INTO messages(room_id, user_id, content, type, media_url) VALUES($1,$2,$3,$4,$5) RETURNING id",
        uuid.UUID(room_id), uuid.UUID(user_id), body.content, body.type, body.mediaUrl,
    )
    await pool.execute("UPDATE rooms SET updated_at=now() WHERE id=$1", uuid.UUID(room_id))

    msg_data = {
        "id": str(msg_id), "roomId": room_id, "userId": user_id,
        "content": body.content, "type": body.type, "mediaUrl": body.mediaUrl,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await _centrifugo_publish(f"room:{room_id}", {"type": "message", "data": msg_data})
    return {"success": True, "messageId": str(msg_id), "data": msg_data}


@app.put("/rooms/{room_id}/messages/{message_id}")
async def edit_message(
    room_id: str,
    message_id: str,
    body: EditMessageRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow("SELECT user_id, content, edit_history FROM messages WHERE id=$1", uuid.UUID(message_id))
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    if str(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not your message")

    import json
    history = list(row["edit_history"]) if row["edit_history"] else []
    history.append({"content": row["content"], "editedAt": datetime.now(timezone.utc).isoformat()})

    await pool.execute(
        "UPDATE messages SET content=$1, is_edited=TRUE, edit_history=$2::jsonb, updated_at=now() WHERE id=$3",
        body.content, json.dumps(history), uuid.UUID(message_id),
    )
    return {"success": True}


@app.delete("/rooms/{room_id}/messages/{message_id}")
async def delete_message(
    room_id: str,
    message_id: str,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow("SELECT user_id FROM messages WHERE id=$1", uuid.UUID(message_id))
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    if str(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not your message")
    await pool.execute("UPDATE messages SET is_deleted=TRUE, content='', updated_at=now() WHERE id=$1", uuid.UUID(message_id))
    await _centrifugo_publish(f"room:{room_id}", {"type": "message_deleted", "data": {"messageId": message_id}})
    return {"success": True}


# ─── Centrifugo token ─────────────────────────────────────────────────────────

@app.get("/centrifugo/token")
async def centrifugo_token(user_id: str = Depends(_user_id)):
    from jose import jwt as jose_jwt
    token = jose_jwt.encode(
        {"sub": user_id, "exp": int((datetime.now(timezone.utc).timestamp()) + 3600)},
        CENTRIFUGO_API_KEY, algorithm="HS256",
    )
    return {"success": True, "token": token}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
