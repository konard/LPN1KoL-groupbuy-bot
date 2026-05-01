import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt as jose_jwt
from pydantic import BaseModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("core")

PORT = int(os.getenv("PORT", "8000"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/groupbuy")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_ALGORITHM = "HS256"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None

MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN CREATE TYPE user_role AS ENUM ('user','organizer','admin','moderator');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE procurement_status AS ENUM ('draft','active','closed','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE payment_status AS ENUM ('pending','completed','failed','refunded');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username          TEXT NOT NULL,
    email             TEXT UNIQUE,
    phone             TEXT,
    language_code     TEXT DEFAULT 'ru',
    role              user_role NOT NULL DEFAULT 'user',
    balance           BIGINT NOT NULL DEFAULT 0,
    selfie_file_id    TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    platform          TEXT,
    platform_id       TEXT,
    session_state     JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(platform, platform_id)
);

CREATE TABLE IF NOT EXISTS categories (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name       TEXT UNIQUE NOT NULL,
    slug       TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO categories(name, slug) VALUES
    ('Electronics', 'electronics'),
    ('Clothing', 'clothing'),
    ('Food', 'food'),
    ('Books', 'books'),
    ('Sports', 'sports'),
    ('Other', 'other')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS procurements (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organizer_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id      UUID REFERENCES categories(id),
    title            TEXT NOT NULL,
    description      TEXT,
    status           procurement_status NOT NULL DEFAULT 'draft',
    min_quantity     INT NOT NULL DEFAULT 1,
    commission_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS procurement_participants (
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(procurement_id, user_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID NOT NULL REFERENCES users(id),
    procurement_id UUID REFERENCES procurements(id),
    amount         BIGINT NOT NULL,
    currency       TEXT NOT NULL DEFAULT 'RUB',
    status         payment_status NOT NULL DEFAULT 'pending',
    provider       TEXT,
    provider_id    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES users(id),
    content        TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_platform ON users(platform, platform_id);
CREATE INDEX IF NOT EXISTS idx_procurements_organizer ON procurements(organizer_id);
CREATE INDEX IF NOT EXISTS idx_messages_procurement ON messages(procurement_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _redis
    retry = 10
    last_exc = None
    while retry > 0:
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
            break
        except Exception as exc:
            last_exc = exc
            import asyncio
            await asyncio.sleep(3)
            retry -= 1
    if not _pool:
        raise RuntimeError(f"DB connection failed: {last_exc}")

    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)

    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Core API started on :%d", PORT)
    yield
    await _pool.close()
    await _redis.aclose()
    logger.info("Core API stopped")


app = FastAPI(
    title="GroupBuy Bot API",
    description="Core REST API for GroupBuy Bot — multi-platform group purchasing",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


def get_pool() -> asyncpg.Pool:
    return _pool


def get_redis() -> aioredis.Redis:
    return _redis


def _user_id_header(x_user_id: Optional[str] = Header(None)) -> str | None:
    return x_user_id


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    email: str | None = None
    phone: str | None = None
    languageCode: str = "ru"
    platform: str | None = None
    platformId: str | None = None


class UpdateUserRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    languageCode: str | None = None
    selfieFileId: str | None = None


class UpdateBalanceRequest(BaseModel):
    delta: int


class SetSessionStateRequest(BaseModel):
    key: str
    value: object


class ClearSessionRequest(BaseModel):
    key: str | None = None


class CreateProcurementRequest(BaseModel):
    title: str
    description: str | None = None
    categoryId: str | None = None
    minQuantity: int = 1
    commissionPct: float = 0.0


class CreatePaymentRequest(BaseModel):
    procurementId: str | None = None
    amount: int
    currency: str = "RUB"
    provider: str | None = None


class CreateMessageRequest(BaseModel):
    content: str


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "core"}


# ─── Users ────────────────────────────────────────────────────────────────────

@app.get("/api/users")
async def list_users(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch("SELECT id, username, email, phone, role, balance, platform, platform_id, is_active, created_at FROM users ORDER BY created_at DESC LIMIT 100")
    return [dict(r) | {"id": str(r["id"])} for r in rows]


@app.post("/api/users", status_code=201)
async def create_user(body: CreateUserRequest, pool: asyncpg.Pool = Depends(get_pool)):
    uid = await pool.fetchval(
        "INSERT INTO users(username, email, phone, language_code, platform, platform_id) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",
        body.username, body.email, body.phone, body.languageCode, body.platform, body.platformId,
    )
    return {"id": str(uid)}


@app.get("/api/users/{user_id}")
async def get_user(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM users WHERE id=$1", uuid.UUID(user_id))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row) | {"id": str(row["id"])}


@app.put("/api/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserRequest, pool: asyncpg.Pool = Depends(get_pool)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"id": user_id}
    field_map = {"username": "username", "email": "email", "phone": "phone",
                 "languageCode": "language_code", "selfieFileId": "selfie_file_id"}
    set_clauses = [f"{field_map[k]}=${i+2}" for i, k in enumerate(updates)]
    vals = list(updates.values())
    await pool.execute(
        f"UPDATE users SET {', '.join(set_clauses)}, updated_at=now() WHERE id=$1",
        uuid.UUID(user_id), *vals,
    )
    return {"id": user_id}


@app.delete("/api/users/{user_id}", status_code=204)
async def delete_user(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    await pool.execute("DELETE FROM users WHERE id=$1", uuid.UUID(user_id))


@app.get("/api/users/by-platform/{platform}/{platform_id}")
async def get_user_by_platform(platform: str, platform_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM users WHERE platform=$1 AND platform_id=$2", platform, platform_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row) | {"id": str(row["id"])}


@app.get("/api/users/search")
async def search_users(q: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, username, email, phone, role FROM users WHERE username ILIKE $1 OR email ILIKE $1 LIMIT 20",
        f"%{q}%",
    )
    return [dict(r) | {"id": str(r["id"])} for r in rows]


@app.get("/api/users/{user_id}/balance")
async def get_user_balance(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    bal = await pool.fetchval("SELECT balance FROM users WHERE id=$1", uuid.UUID(user_id))
    if bal is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"userId": user_id, "balance": bal, "currency": "RUB"}


@app.patch("/api/users/{user_id}/balance")
async def update_user_balance(user_id: str, body: UpdateBalanceRequest, pool: asyncpg.Pool = Depends(get_pool)):
    new_bal = await pool.fetchval(
        "UPDATE users SET balance=balance+$1, updated_at=now() WHERE id=$2 RETURNING balance",
        body.delta, uuid.UUID(user_id),
    )
    return {"userId": user_id, "balance": new_bal}


@app.get("/api/users/{user_id}/role")
async def get_user_role(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    role = await pool.fetchval("SELECT role FROM users WHERE id=$1", uuid.UUID(user_id))
    return {"userId": user_id, "role": role or "user"}


@app.get("/api/users/{user_id}/ws-token")
async def get_ws_token(user_id: str):
    token = jose_jwt.encode(
        {"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    return {"token": token}


@app.post("/api/users/{user_id}/session-state")
async def set_session_state(user_id: str, body: SetSessionStateRequest, pool: asyncpg.Pool = Depends(get_pool)):
    import json
    row = await pool.fetchrow("SELECT session_state FROM users WHERE id=$1", uuid.UUID(user_id))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    state = dict(row["session_state"] or {})
    state[body.key] = body.value
    await pool.execute(
        "UPDATE users SET session_state=$1::jsonb, updated_at=now() WHERE id=$2",
        json.dumps(state), uuid.UUID(user_id),
    )
    return {"userId": user_id, "sessionState": state}


@app.delete("/api/users/{user_id}/session-state")
async def clear_session_state(user_id: str, body: ClearSessionRequest, pool: asyncpg.Pool = Depends(get_pool)):
    import json
    row = await pool.fetchrow("SELECT session_state FROM users WHERE id=$1", uuid.UUID(user_id))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    state = dict(row["session_state"] or {})
    if body.key:
        state.pop(body.key, None)
    else:
        state = {}
    await pool.execute(
        "UPDATE users SET session_state=$1::jsonb, updated_at=now() WHERE id=$2",
        json.dumps(state), uuid.UUID(user_id),
    )
    return {"userId": user_id, "sessionState": state}


# ─── Procurements ─────────────────────────────────────────────────────────────

@app.get("/api/procurements")
async def list_procurements(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT p.*, u.username as organizer_name FROM procurements p JOIN users u ON u.id=p.organizer_id ORDER BY p.created_at DESC LIMIT 100"
    )
    return [dict(r) | {"id": str(r["id"]), "organizerId": str(r["organizer_id"])} for r in rows]


@app.post("/api/procurements", status_code=201)
async def create_procurement(
    body: CreateProcurementRequest,
    x_user_id: str | None = Header(None),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    pid = await pool.fetchval(
        "INSERT INTO procurements(organizer_id, title, description, category_id, min_quantity, commission_pct) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",
        uuid.UUID(x_user_id), body.title, body.description,
        uuid.UUID(body.categoryId) if body.categoryId else None,
        body.minQuantity, body.commissionPct,
    )
    return {"id": str(pid)}


@app.get("/api/procurements/{procurement_id}")
async def get_procurement(procurement_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM procurements WHERE id=$1", uuid.UUID(procurement_id))
    if not row:
        raise HTTPException(status_code=404, detail="Procurement not found")
    return dict(row) | {"id": str(row["id"]), "organizerId": str(row["organizer_id"])}


@app.get("/api/users/{user_id}/procurements")
async def get_user_procurements(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT * FROM procurements WHERE organizer_id=$1 ORDER BY created_at DESC",
        uuid.UUID(user_id),
    )
    return [dict(r) | {"id": str(r["id"])} for r in rows]


@app.post("/api/procurements/{procurement_id}/join")
async def join_procurement(
    procurement_id: str,
    x_user_id: str | None = Header(None),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    await pool.execute(
        "INSERT INTO procurement_participants(procurement_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
        uuid.UUID(procurement_id), uuid.UUID(x_user_id),
    )
    return {"success": True}


@app.post("/api/procurements/{procurement_id}/leave")
async def leave_procurement(
    procurement_id: str,
    x_user_id: str | None = Header(None),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    await pool.execute(
        "DELETE FROM procurement_participants WHERE procurement_id=$1 AND user_id=$2",
        uuid.UUID(procurement_id), uuid.UUID(x_user_id),
    )
    return {"success": True}


@app.get("/api/categories")
async def list_categories(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch("SELECT id, name, slug FROM categories ORDER BY name")
    return [dict(r) | {"id": str(r["id"])} for r in rows]


# ─── Payments ─────────────────────────────────────────────────────────────────

@app.post("/api/payments", status_code=201)
async def create_payment(
    body: CreatePaymentRequest,
    x_user_id: str | None = Header(None),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    pay_id = await pool.fetchval(
        "INSERT INTO payments(user_id, procurement_id, amount, currency, provider) VALUES($1,$2,$3,$4,$5) RETURNING id",
        uuid.UUID(x_user_id),
        uuid.UUID(body.procurementId) if body.procurementId else None,
        body.amount, body.currency, body.provider,
    )
    return {"id": str(pay_id), "status": "pending"}


@app.get("/api/payments/{payment_id}")
async def get_payment_status(payment_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT id, status, amount, currency, created_at FROM payments WHERE id=$1", uuid.UUID(payment_id))
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")
    return dict(row) | {"id": str(row["id"])}


# ─── Chat ─────────────────────────────────────────────────────────────────────

@app.get("/api/procurements/{procurement_id}/messages")
async def list_messages(procurement_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, user_id, content, created_at FROM messages WHERE procurement_id=$1 ORDER BY created_at DESC LIMIT 50",
        uuid.UUID(procurement_id),
    )
    return [dict(r) | {"id": str(r["id"]), "userId": str(r["user_id"])} for r in reversed(rows)]


@app.post("/api/procurements/{procurement_id}/messages", status_code=201)
async def create_message(
    procurement_id: str,
    body: CreateMessageRequest,
    x_user_id: str | None = Header(None),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    msg_id = await pool.fetchval(
        "INSERT INTO messages(procurement_id, user_id, content) VALUES($1,$2,$3) RETURNING id",
        uuid.UUID(procurement_id), uuid.UUID(x_user_id), body.content,
    )
    return {"id": str(msg_id)}


@app.get("/api/users/{user_id}/notifications")
async def list_notifications(user_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, text, is_read, created_at FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50",
        uuid.UUID(user_id),
    )
    return [dict(r) | {"id": str(r["id"])} for r in rows]


# ─── WebSocket ────────────────────────────────────────────────────────────────

_ws_connections: dict[str, set[WebSocket]] = {}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str | None = None):
    if token:
        try:
            jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except Exception:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    if user_id not in _ws_connections:
        _ws_connections[user_id] = set()
    _ws_connections[user_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # echo back for now; real impl would route messages
            await websocket.send_text(data)
    except WebSocketDisconnect:
        _ws_connections[user_id].discard(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
