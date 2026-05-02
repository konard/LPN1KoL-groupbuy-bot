import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])

_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None

CHAT_MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE chat_room_type AS ENUM ('purchase','direct','group');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE chat_msg_type AS ENUM ('text','system','image','video','file');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS chat_rooms (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    type        chat_room_type NOT NULL DEFAULT 'group',
    purchase_id UUID,
    created_by  UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_room_members (
    room_id    UUID NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (room_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id      UUID NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL,
    content      TEXT NOT NULL DEFAULT '',
    type         chat_msg_type NOT NULL DEFAULT 'text',
    media_url    TEXT,
    is_edited    BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    edit_history JSONB NOT NULL DEFAULT '[]',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages(room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_room_members_user ON chat_room_members(user_id);
"""


async def get_chat_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = settings.database_url.replace("+asyncpg", "")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(CHAT_MIGRATIONS)
    return _pool


async def get_chat_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def _centrifugo_publish(channel: str, data: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.centrifugo_url}/api/publish",
                headers={"X-API-Key": settings.centrifugo_api_key, "Content-Type": "application/json"},
                json={"channel": channel, "data": data},
            )
    except Exception:
        pass


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


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


@router.post("/rooms", status_code=201, summary="Create a chat room")
async def create_room(
    body: CreateRoomRequest,
    user_id: str = Depends(_get_user_id),
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    async with pool.acquire() as conn:
        async with conn.transaction():
            room_id = await conn.fetchval(
                "INSERT INTO chat_rooms(name, type, purchase_id, created_by) VALUES($1,$2,$3,$4) RETURNING id",
                body.name, body.type,
                uuid.UUID(body.purchaseId) if body.purchaseId else None,
                uuid.UUID(user_id),
            )
            member_ids = list({user_id} | set(body.memberIds))
            await conn.executemany(
                "INSERT INTO chat_room_members(room_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
                [(room_id, uuid.UUID(mid)) for mid in member_ids],
            )
    return {"success": True, "roomId": str(room_id)}


@router.get("/rooms", summary="List rooms for current user")
async def list_rooms(
    user_id: str = Depends(_get_user_id),
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    rows = await pool.fetch(
        """SELECT r.id, r.name, r.type, r.purchase_id, r.is_archived, r.created_at
           FROM chat_rooms r
           JOIN chat_room_members rm ON rm.room_id = r.id
           WHERE rm.user_id = $1
           ORDER BY r.updated_at DESC""",
        uuid.UUID(user_id),
    )
    return {"success": True, "data": [
        dict(r) | {"id": str(r["id"]), "purchaseId": str(r["purchase_id"]) if r["purchase_id"] else None}
        for r in rows
    ]}


@router.post("/rooms/{room_id}/members/{member_id}", summary="Add a member to a room")
async def add_member(
    room_id: str,
    member_id: str,
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    await pool.execute(
        "INSERT INTO chat_room_members(room_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
        uuid.UUID(room_id), uuid.UUID(member_id),
    )
    return {"success": True}


@router.get("/rooms/{room_id}/messages", summary="List messages in a room")
async def list_messages(
    room_id: str,
    limit: int = 50,
    before: str | None = None,
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    if before:
        rows = await pool.fetch(
            "SELECT * FROM chat_messages WHERE room_id=$1 AND created_at < $2 AND NOT is_deleted ORDER BY created_at DESC LIMIT $3",
            uuid.UUID(room_id), datetime.fromisoformat(before), limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM chat_messages WHERE room_id=$1 AND NOT is_deleted ORDER BY created_at DESC LIMIT $2",
            uuid.UUID(room_id), limit,
        )
    return {"success": True, "data": [
        dict(r) | {"id": str(r["id"]), "roomId": str(r["room_id"]), "userId": str(r["user_id"])}
        for r in reversed(rows)
    ]}


@router.post("/rooms/{room_id}/messages", status_code=201, summary="Send a message")
async def send_message(
    room_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(_get_user_id),
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    msg_id = await pool.fetchval(
        "INSERT INTO chat_messages(room_id, user_id, content, type, media_url) VALUES($1,$2,$3,$4,$5) RETURNING id",
        uuid.UUID(room_id), uuid.UUID(user_id), body.content, body.type, body.mediaUrl,
    )
    await pool.execute("UPDATE chat_rooms SET updated_at=now() WHERE id=$1", uuid.UUID(room_id))
    msg_data = {
        "id": str(msg_id), "roomId": room_id, "userId": user_id,
        "content": body.content, "type": body.type, "mediaUrl": body.mediaUrl,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await _centrifugo_publish(f"room:{room_id}", {"type": "message", "data": msg_data})
    return {"success": True, "messageId": str(msg_id), "data": msg_data}


@router.put("/rooms/{room_id}/messages/{message_id}", summary="Edit a message")
async def edit_message(
    room_id: str,
    message_id: str,
    body: EditMessageRequest,
    user_id: str = Depends(_get_user_id),
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    row = await pool.fetchrow(
        "SELECT user_id, content, edit_history FROM chat_messages WHERE id=$1",
        uuid.UUID(message_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    if str(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not your message")
    history = list(row["edit_history"]) if row["edit_history"] else []
    history.append({"content": row["content"], "editedAt": datetime.now(timezone.utc).isoformat()})
    await pool.execute(
        "UPDATE chat_messages SET content=$1, is_edited=TRUE, edit_history=$2::jsonb, updated_at=now() WHERE id=$3",
        body.content, json.dumps(history), uuid.UUID(message_id),
    )
    return {"success": True}


@router.delete("/rooms/{room_id}/messages/{message_id}", summary="Delete a message")
async def delete_message(
    room_id: str,
    message_id: str,
    user_id: str = Depends(_get_user_id),
    pool: asyncpg.Pool = Depends(get_chat_pool),
):
    row = await pool.fetchrow("SELECT user_id FROM chat_messages WHERE id=$1", uuid.UUID(message_id))
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    if str(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not your message")
    await pool.execute(
        "UPDATE chat_messages SET is_deleted=TRUE, content='', updated_at=now() WHERE id=$1",
        uuid.UUID(message_id),
    )
    await _centrifugo_publish(f"room:{room_id}", {"type": "message_deleted", "data": {"messageId": message_id}})
    return {"success": True}


@router.get("/centrifugo/token", summary="Get Centrifugo WebSocket token")
async def centrifugo_token(user_id: str = Depends(_get_user_id)):
    from jose import jwt as jose_jwt
    token = jose_jwt.encode(
        {"sub": user_id, "exp": int(datetime.now(timezone.utc).timestamp()) + 3600},
        settings.centrifugo_api_key, algorithm="HS256",
    )
    return {"success": True, "token": token}


async def close_chat_connections() -> None:
    global _pool, _redis
    if _pool:
        await _pool.close()
        _pool = None
    if _redis:
        await _redis.aclose()
        _redis = None
