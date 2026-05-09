import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("payment-service")

PORT = int(os.getenv("PORT", "4003"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/payment_db")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

_pool: asyncpg.Pool | None = None
_producer: AIOKafkaProducer | None = None

MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE wallet_status AS ENUM ('active','frozen','closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tx_type AS ENUM ('top_up','hold','commit','release','withdraw','refund','escrow_in','escrow_out','commission');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE escrow_status AS ENUM ('active','released','disputed','refunded');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE commission_status AS ENUM ('held','committed','released');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tx_status AS ENUM ('pending','completed','failed','rolled_back');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS wallets (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL UNIQUE,
    balance    BIGINT NOT NULL DEFAULT 0,
    on_hold    BIGINT NOT NULL DEFAULT 0,
    status     wallet_status NOT NULL DEFAULT 'active',
    currency   TEXT NOT NULL DEFAULT 'RUB',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id    UUID NOT NULL REFERENCES wallets(id),
    type         tx_type NOT NULL,
    amount       BIGINT NOT NULL,
    status       tx_status NOT NULL DEFAULT 'pending',
    reference_id UUID,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escrow_accounts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id             UUID NOT NULL UNIQUE,
    total_deposited         BIGINT NOT NULL DEFAULT 0,
    confirmations_received  INT NOT NULL DEFAULT 0,
    confirmations_required  INT NOT NULL DEFAULT 2,
    status                  escrow_status NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS commissions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id UUID NOT NULL,
    amount      BIGINT NOT NULL,
    percent     NUMERIC(5,2) NOT NULL DEFAULT 0,
    status      commission_status NOT NULL DEFAULT 'held',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_wallet_id ON transactions(wallet_id);
"""


async def _publish(topic: str, payload: dict) -> None:
    if _producer:
        try:
            await _producer.send_and_wait(topic, value=json.dumps(payload).encode())
        except Exception as exc:
            logger.error("Kafka publish failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _producer
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)

    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKERS, acks="all", enable_idempotence=True)
    try:
        await _producer.start()
    except Exception as exc:
        logger.warning("Kafka unavailable: %s", exc)
        _producer = None

    logger.info("Payment service started on :%d", PORT)
    yield

    if _producer:
        await _producer.stop()
    await _pool.close()
    logger.info("Payment service stopped")


app = FastAPI(title="Payment Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pool() -> asyncpg.Pool:
    return _pool


def _user_id(x_user_id: Optional[str] = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TopUpRequest(BaseModel):
    amount: int
    currency: str = "RUB"


class HoldRequest(BaseModel):
    amount: int
    purchaseId: str


class CommitRequest(BaseModel):
    purchaseId: str


class ReleaseRequest(BaseModel):
    purchaseId: str


class EscrowDepositRequest(BaseModel):
    purchaseId: str
    amount: int
    userId: str


class EscrowConfirmRequest(BaseModel):
    purchaseId: str
    confirmerId: str


# ─── Wallet Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "payment-service"}


@app.get("/wallets/me")
async def get_my_wallet(user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM wallets WHERE user_id=$1", uuid.UUID(user_id))
    if not row:
        # Auto-create wallet on first access
        row_id = await pool.fetchval(
            "INSERT INTO wallets(user_id) VALUES($1) ON CONFLICT(user_id) DO UPDATE SET updated_at=now() RETURNING id",
            uuid.UUID(user_id),
        )
        row = await pool.fetchrow("SELECT * FROM wallets WHERE id=$1", row_id)
    return {"success": True, "data": {
        "id": str(row["id"]), "userId": str(row["user_id"]),
        "balance": row["balance"], "onHold": row["on_hold"],
        "status": row["status"], "currency": row["currency"],
    }}


@app.post("/wallets/topup")
async def top_up(body: TopUpRequest, user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await conn.fetchrow(
                "INSERT INTO wallets(user_id) VALUES($1) ON CONFLICT(user_id) DO UPDATE SET balance=wallets.balance+$2, updated_at=now() RETURNING id, balance",
                uuid.UUID(user_id), body.amount,
            )
            tx_id = await conn.fetchval(
                "INSERT INTO transactions(wallet_id, type, amount, status) VALUES($1,'top_up',$2,'completed') RETURNING id",
                wallet["id"], body.amount,
            )
    await _publish("payment.topup.completed", {
        "userId": user_id, "walletId": str(wallet["id"]),
        "amount": body.amount, "currency": body.currency,
        "transactionId": str(tx_id), "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "balance": wallet["balance"], "transactionId": str(tx_id)}


@app.post("/wallets/hold")
async def hold_funds(body: HoldRequest, user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await conn.fetchrow("SELECT id, balance, on_hold FROM wallets WHERE user_id=$1 FOR UPDATE", uuid.UUID(user_id))
            if not wallet or wallet["balance"] < body.amount:
                raise HTTPException(status_code=402, detail="Insufficient balance")
            await conn.execute(
                "UPDATE wallets SET balance=balance-$1, on_hold=on_hold+$1, updated_at=now() WHERE id=$2",
                body.amount, wallet["id"],
            )
            tx_id = await conn.fetchval(
                "INSERT INTO transactions(wallet_id, type, amount, status, reference_id) VALUES($1,'hold',$2,'completed',$3) RETURNING id",
                wallet["id"], body.amount, uuid.UUID(body.purchaseId),
            )
    await _publish("payment.hold.created", {
        "userId": user_id, "walletId": str(wallet["id"]),
        "amount": body.amount, "purchaseId": body.purchaseId,
        "transactionId": str(tx_id), "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "transactionId": str(tx_id)}


@app.post("/wallets/commit")
async def commit_funds(body: CommitRequest, user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await conn.fetchrow("SELECT id, on_hold FROM wallets WHERE user_id=$1 FOR UPDATE", uuid.UUID(user_id))
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            tx = await conn.fetchrow(
                "SELECT id, amount FROM transactions WHERE wallet_id=$1 AND type='hold' AND reference_id=$2 AND status='completed'",
                wallet["id"], uuid.UUID(body.purchaseId),
            )
            if not tx:
                raise HTTPException(status_code=404, detail="Hold not found")
            await conn.execute(
                "UPDATE wallets SET on_hold=on_hold-$1, updated_at=now() WHERE id=$2",
                tx["amount"], wallet["id"],
            )
            tx_id = await conn.fetchval(
                "INSERT INTO transactions(wallet_id, type, amount, status, reference_id) VALUES($1,'commit',$2,'completed',$3) RETURNING id",
                wallet["id"], tx["amount"], uuid.UUID(body.purchaseId),
            )
    await _publish("payment.committed", {
        "userId": user_id, "walletId": str(wallet["id"]),
        "amount": tx["amount"], "purchaseId": body.purchaseId,
        "transactionId": str(tx_id), "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "transactionId": str(tx_id)}


@app.post("/wallets/release")
async def release_funds(body: ReleaseRequest, user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await conn.fetchrow("SELECT id FROM wallets WHERE user_id=$1 FOR UPDATE", uuid.UUID(user_id))
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            tx = await conn.fetchrow(
                "SELECT id, amount FROM transactions WHERE wallet_id=$1 AND type='hold' AND reference_id=$2 AND status='completed'",
                wallet["id"], uuid.UUID(body.purchaseId),
            )
            if not tx:
                raise HTTPException(status_code=404, detail="Hold not found")
            await conn.execute(
                "UPDATE wallets SET balance=balance+$1, on_hold=on_hold-$1, updated_at=now() WHERE id=$2",
                tx["amount"], wallet["id"],
            )
            tx_id = await conn.fetchval(
                "INSERT INTO transactions(wallet_id, type, amount, status, reference_id) VALUES($1,'release',$2,'completed',$3) RETURNING id",
                wallet["id"], tx["amount"], uuid.UUID(body.purchaseId),
            )
    await _publish("payment.released", {
        "userId": user_id, "walletId": str(wallet["id"]),
        "amount": tx["amount"], "purchaseId": body.purchaseId,
        "transactionId": str(tx_id), "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "transactionId": str(tx_id)}


# ─── Escrow Endpoints ─────────────────────────────────────────────────────────

@app.post("/escrow/deposit")
async def escrow_deposit(body: EscrowDepositRequest, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            escrow = await conn.fetchrow(
                """INSERT INTO escrow_accounts(purchase_id, total_deposited)
                   VALUES($1, $2)
                   ON CONFLICT(purchase_id) DO UPDATE SET total_deposited=escrow_accounts.total_deposited+$2, updated_at=now()
                   RETURNING id, total_deposited, confirmations_required""",
                uuid.UUID(body.purchaseId), body.amount,
            )
    await _publish("escrow.deposited", {
        "purchaseId": body.purchaseId, "userId": body.userId,
        "amount": body.amount, "totalDeposited": escrow["total_deposited"],
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "escrowId": str(escrow["id"]), "totalDeposited": escrow["total_deposited"]}


@app.post("/escrow/confirm")
async def escrow_confirm(body: EscrowConfirmRequest, pool: asyncpg.Pool = Depends(get_pool)):
    escrow = await pool.fetchrow("SELECT * FROM escrow_accounts WHERE purchase_id=$1", uuid.UUID(body.purchaseId))
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    new_confirmations = escrow["confirmations_received"] + 1
    await pool.execute(
        "UPDATE escrow_accounts SET confirmations_received=$1, updated_at=now() WHERE id=$2",
        new_confirmations, escrow["id"],
    )
    await _publish("escrow.confirmed", {
        "purchaseId": body.purchaseId, "confirmerId": body.confirmerId,
        "confirmationsReceived": new_confirmations,
        "confirmationsRequired": escrow["confirmations_required"],
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "confirmations": new_confirmations, "required": escrow["confirmations_required"]}


@app.post("/escrow/release")
async def escrow_release(body: ReleaseRequest, pool: asyncpg.Pool = Depends(get_pool)):
    await pool.execute(
        "UPDATE escrow_accounts SET status='released', updated_at=now() WHERE purchase_id=$1",
        uuid.UUID(body.purchaseId),
    )
    await _publish("escrow.released", {
        "purchaseId": body.purchaseId, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True}


@app.get("/transactions")
async def list_transactions(user_id: str = Depends(_user_id), pool: asyncpg.Pool = Depends(get_pool)):
    wallet = await pool.fetchrow("SELECT id FROM wallets WHERE user_id=$1", uuid.UUID(user_id))
    if not wallet:
        return {"success": True, "data": []}
    rows = await pool.fetch(
        "SELECT id, type, amount, status, reference_id, description, created_at FROM transactions WHERE wallet_id=$1 ORDER BY created_at DESC LIMIT 50",
        wallet["id"],
    )
    return {"success": True, "data": [
        dict(r) | {"id": str(r["id"]), "referenceId": str(r["reference_id"]) if r["reference_id"] else None}
        for r in rows
    ]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
