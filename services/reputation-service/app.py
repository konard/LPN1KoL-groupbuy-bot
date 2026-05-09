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
logger = logging.getLogger("reputation-service")

PORT = int(os.getenv("PORT", "4008"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/reputation_db")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

_pool: asyncpg.Pool | None = None
_producer: AIOKafkaProducer | None = None

MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE complaint_status AS ENUM ('open','investigating','resolved','dismissed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS reviews (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    author_id     UUID NOT NULL,
    target_id     UUID NOT NULL,
    purchase_id   UUID,
    rating        SMALLINT NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment       TEXT,
    is_anonymous  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS complaints (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reporter_id  UUID NOT NULL,
    target_id    UUID NOT NULL,
    purchase_id  UUID,
    reason       TEXT NOT NULL,
    evidence_url TEXT,
    status       complaint_status NOT NULL DEFAULT 'open',
    resolution   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reputation_scores (
    user_id      UUID PRIMARY KEY,
    score        NUMERIC(5,2) NOT NULL DEFAULT 5.0,
    total_reviews INT NOT NULL DEFAULT 0,
    total_complaints INT NOT NULL DEFAULT 0,
    is_blocked   BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_target ON reviews(target_id);
CREATE INDEX IF NOT EXISTS idx_complaints_target ON complaints(target_id);
"""

AUTO_BLOCK_THRESHOLD = 5  # block after 5 unresolved complaints


async def _publish(topic: str, payload: dict) -> None:
    if _producer:
        try:
            await _producer.send_and_wait(topic, value=json.dumps(payload).encode())
        except Exception as exc:
            logger.error("Kafka publish failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _producer
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)

    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKERS, acks="all", enable_idempotence=True)
    try:
        await _producer.start()
    except Exception as exc:
        logger.warning("Kafka unavailable: %s", exc)
        _producer = None

    logger.info("Reputation service started on :%d", PORT)
    yield

    if _producer:
        await _producer.stop()
    await _pool.close()
    logger.info("Reputation service stopped")


app = FastAPI(title="Reputation Service", version="1.0.0", lifespan=lifespan)
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

class CreateReviewRequest(BaseModel):
    targetId: str
    purchaseId: str | None = None
    rating: int
    comment: str | None = None
    isAnonymous: bool = False


class CreateComplaintRequest(BaseModel):
    targetId: str
    purchaseId: str | None = None
    reason: str
    evidenceUrl: str | None = None


class ResolveComplaintRequest(BaseModel):
    resolution: str
    status: str = "resolved"


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _update_score(target_id: uuid.UUID, pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            avg = await conn.fetchval("SELECT AVG(rating)::NUMERIC(5,2) FROM reviews WHERE target_id=$1", target_id)
            count = await conn.fetchval("SELECT COUNT(*) FROM reviews WHERE target_id=$1", target_id)
            complaints = await conn.fetchval(
                "SELECT COUNT(*) FROM complaints WHERE target_id=$1 AND status NOT IN ('resolved','dismissed')", target_id
            )
            is_blocked = int(complaints) >= AUTO_BLOCK_THRESHOLD

            await conn.execute(
                """INSERT INTO reputation_scores(user_id, score, total_reviews, total_complaints, is_blocked)
                   VALUES($1, $2, $3, $4, $5)
                   ON CONFLICT(user_id) DO UPDATE SET
                     score=$2, total_reviews=$3, total_complaints=$4, is_blocked=$5, updated_at=now()""",
                target_id, float(avg or 5.0), int(count), int(complaints), is_blocked,
            )

            if is_blocked:
                await _publish("user.auto_blocked", {
                    "userId": str(target_id), "reason": "Too many unresolved complaints",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })


# ─── Reviews ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "reputation-service"}


@app.post("/reviews", status_code=201)
async def create_review(
    body: CreateReviewRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    review_id = await pool.fetchval(
        "INSERT INTO reviews(author_id, target_id, purchase_id, rating, comment, is_anonymous) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",
        uuid.UUID(user_id), uuid.UUID(body.targetId),
        uuid.UUID(body.purchaseId) if body.purchaseId else None,
        body.rating, body.comment, body.isAnonymous,
    )
    await _update_score(uuid.UUID(body.targetId), pool)
    await _publish("review.created", {
        "reviewId": str(review_id), "authorId": user_id,
        "targetId": body.targetId, "rating": body.rating,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "reviewId": str(review_id)}


@app.get("/reviews/{user_id_param}")
async def get_user_reviews(user_id_param: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, author_id, rating, comment, is_anonymous, created_at FROM reviews WHERE target_id=$1 ORDER BY created_at DESC",
        uuid.UUID(user_id_param),
    )
    return {"success": True, "data": [
        dict(r) | {
            "id": str(r["id"]),
            "authorId": str(r["author_id"]) if not r["is_anonymous"] else None,
        }
        for r in rows
    ]}


# ─── Complaints ───────────────────────────────────────────────────────────────

@app.post("/complaints", status_code=201)
async def create_complaint(
    body: CreateComplaintRequest,
    user_id: str = Depends(_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
):
    complaint_id = await pool.fetchval(
        "INSERT INTO complaints(reporter_id, target_id, purchase_id, reason, evidence_url) VALUES($1,$2,$3,$4,$5) RETURNING id",
        uuid.UUID(user_id), uuid.UUID(body.targetId),
        uuid.UUID(body.purchaseId) if body.purchaseId else None,
        body.reason, body.evidenceUrl,
    )
    await _update_score(uuid.UUID(body.targetId), pool)
    await _publish("complaint.filed", {
        "complaintId": str(complaint_id), "reporterId": user_id,
        "targetId": body.targetId, "reason": body.reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "complaintId": str(complaint_id)}


@app.patch("/complaints/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: str,
    body: ResolveComplaintRequest,
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow("SELECT target_id FROM complaints WHERE id=$1", uuid.UUID(complaint_id))
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")
    await pool.execute(
        "UPDATE complaints SET status=$1, resolution=$2, updated_at=now() WHERE id=$3",
        body.status, body.resolution, uuid.UUID(complaint_id),
    )
    await _update_score(row["target_id"], pool)
    await _publish("complaint.resolved", {
        "complaintId": complaint_id, "targetId": str(row["target_id"]),
        "status": body.status, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True}


@app.get("/scores/{user_id_param}")
async def get_score(user_id_param: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM reputation_scores WHERE user_id=$1", uuid.UUID(user_id_param))
    if not row:
        return {"success": True, "data": {"userId": user_id_param, "score": 5.0, "totalReviews": 0, "isBlocked": False}}
    return {"success": True, "data": {
        "userId": str(row["user_id"]), "score": float(row["score"]),
        "totalReviews": row["total_reviews"], "totalComplaints": row["total_complaints"],
        "isBlocked": row["is_blocked"],
    }}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
