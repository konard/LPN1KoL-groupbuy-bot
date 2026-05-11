import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import asyncpg
from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purchase-service")

PORT = int(os.getenv("PORT", "4002"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/purchase_db")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "purchase-service")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

_pool: asyncpg.Pool | None = None
_producer: AIOKafkaProducer | None = None

# Schema is provisioned by entrypoint.sh via SQL files in /app/migrations/.
# Keeping migrations in a single source of truth prevents schema drift between
# the file-based migrations (which use `voting_session_id`, `commission_percent`,
# `min_participants`, etc.) and any inline SQL run at application startup.


async def _publish(topic: str, payload: dict) -> None:
    if _producer:
        await _producer.send_and_wait(
            topic,
            value=json.dumps(payload).encode(),
            key=payload.get("purchaseId", "").encode() if payload.get("purchaseId") else None,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _producer
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

    _producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BROKERS,
        client_id=KAFKA_CLIENT_ID,
        acks="all",
        enable_idempotence=True,
    )
    try:
        await _producer.start()
    except Exception as exc:
        logger.warning("Kafka unavailable at startup: %s", exc)
        _producer = None

    logger.info("Purchase service started on :%d", PORT)
    yield

    if _producer:
        await _producer.stop()
    await _pool.close()
    logger.info("Purchase service stopped")


app = FastAPI(title="Purchase Service", version="1.0.0", lifespan=lifespan)
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

class CreatePurchaseRequest(BaseModel):
    title: str
    description: str | None = None
    category: str | None = None
    minQuantity: int = 1
    commissionPct: float = 0.0


class AddCandidateRequest(BaseModel):
    supplierName: str
    price: float
    description: str | None = None


class CastVoteRequest(BaseModel):
    candidateId: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "purchase-service"}


@app.post("/purchases", status_code=201)
async def create_purchase(
    body: CreatePurchaseRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    pid = await pool.fetchval(
        """INSERT INTO purchases(organizer_id, title, description, category, min_participants, commission_percent)
           VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",
        uuid.UUID(user_id), body.title, body.description, body.category,
        body.minQuantity, body.commissionPct,
    )
    await _publish("purchase.created", {
        "purchaseId": str(pid), "organizerId": user_id,
        "title": body.title, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "purchaseId": str(pid)}


@app.get("/purchases")
async def list_purchases(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, organizer_id, title, description, category, status, min_participants, commission_percent, created_at FROM purchases ORDER BY created_at DESC LIMIT 100"
    )
    return {"success": True, "data": [dict(r) | {"id": str(r["id"]), "organizer_id": str(r["organizer_id"])} for r in rows]}


@app.get("/purchases/{purchase_id}")
async def get_purchase(purchase_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM purchases WHERE id=$1", uuid.UUID(purchase_id))
    if not row:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return {"success": True, "data": dict(row) | {"id": str(row["id"]), "organizer_id": str(row["organizer_id"])}}


@app.post("/purchases/{purchase_id}/voting-sessions", status_code=201)
async def start_voting(
    purchase_id: str,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow("SELECT organizer_id FROM purchases WHERE id=$1", uuid.UUID(purchase_id))
    if not row:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if str(row["organizer_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Only organizer can start voting")

    closes_at = datetime.now(timezone.utc) + timedelta(hours=24)
    session_id = await pool.fetchval(
        "INSERT INTO voting_sessions(purchase_id, closes_at) VALUES($1, $2) RETURNING id",
        uuid.UUID(purchase_id), closes_at,
    )
    await pool.execute("UPDATE purchases SET status='voting', updated_at=now() WHERE id=$1", uuid.UUID(purchase_id))
    await _publish("purchase.voting.started", {
        "purchaseId": purchase_id, "sessionId": str(session_id),
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "sessionId": str(session_id)}


@app.post("/purchases/{purchase_id}/voting-sessions/{session_id}/candidates", status_code=201)
async def add_candidate(
    purchase_id: str,
    session_id: str,
    body: AddCandidateRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    cid = await pool.fetchval(
        """INSERT INTO candidates(voting_session_id, supplier_name, price_per_unit, description, proposed_by)
           VALUES($1,$2,$3,$4,$5) RETURNING id""",
        uuid.UUID(session_id), body.supplierName, body.price, body.description, uuid.UUID(user_id),
    )
    await _publish("purchase.candidate.added", {
        "purchaseId": purchase_id, "sessionId": session_id,
        "candidateId": str(cid), "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "candidateId": str(cid)}


@app.post("/purchases/{purchase_id}/voting-sessions/{session_id}/vote")
async def cast_vote(
    purchase_id: str,
    session_id: str,
    body: CastVoteRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    try:
        await pool.execute(
            "INSERT INTO votes(voting_session_id, user_id, candidate_id) VALUES($1,$2,$3)",
            uuid.UUID(session_id), uuid.UUID(user_id), uuid.UUID(body.candidateId),
        )
    except asyncpg.UniqueViolationError:
        await pool.execute(
            "UPDATE votes SET candidate_id=$1 WHERE voting_session_id=$2 AND user_id=$3",
            uuid.UUID(body.candidateId), uuid.UUID(session_id), uuid.UUID(user_id),
        )
        await _publish("purchase.vote.changed", {
            "purchaseId": purchase_id, "sessionId": session_id,
            "userId": user_id, "newCandidateId": body.candidateId,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True, "action": "changed"}

    total_votes = await pool.fetchval(
        "SELECT COUNT(*) FROM votes WHERE voting_session_id=$1", uuid.UUID(session_id)
    )
    await _publish("purchase.vote.cast", {
        "purchaseId": purchase_id, "sessionId": session_id,
        "userId": user_id, "candidateId": body.candidateId,
        "totalVotes": total_votes, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "action": "cast"}


@app.post("/purchases/{purchase_id}/voting-sessions/{session_id}/close")
async def close_voting(
    purchase_id: str,
    session_id: str,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    rows = await pool.fetch(
        "SELECT candidate_id, COUNT(*) as cnt FROM votes WHERE voting_session_id=$1 GROUP BY candidate_id ORDER BY cnt DESC",
        uuid.UUID(session_id),
    )

    if not rows:
        await _publish("purchase.voting.closed", {
            "purchaseId": purchase_id, "sessionId": session_id,
            "winnerId": None, "totalVotes": 0, "ts": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True, "winnerId": None}

    winner_id = str(rows[0]["candidate_id"])
    total_votes = sum(r["cnt"] for r in rows)
    is_tie = len(rows) > 1 and rows[0]["cnt"] == rows[1]["cnt"]

    await pool.execute(
        "UPDATE voting_sessions SET status='closed', winner_candidate_id=$1 WHERE id=$2",
        uuid.UUID(winner_id), uuid.UUID(session_id),
    )

    event = "purchase.voting.tie" if is_tie else "purchase.voting.closed"
    await _publish(event, {
        "purchaseId": purchase_id, "sessionId": session_id,
        "winnerId": winner_id, "totalVotes": total_votes,
        "isTie": is_tie, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "winnerId": winner_id, "totalVotes": total_votes, "isTie": is_tie}


@app.post("/purchases/{purchase_id}/cancel")
async def cancel_purchase(
    purchase_id: str,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow("SELECT organizer_id FROM purchases WHERE id=$1", uuid.UUID(purchase_id))
    if not row:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if str(row["organizer_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Only organizer can cancel")
    await pool.execute("UPDATE purchases SET status='cancelled', updated_at=now() WHERE id=$1", uuid.UUID(purchase_id))
    await _publish("purchase.cancelled", {
        "purchaseId": purchase_id, "userId": user_id, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
