import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import httpx

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auth-service")

PORT = int(os.getenv("PORT", "4001"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/auth_db")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "change_me_refresh")
JWT_EXPIRES_IN = int(os.getenv("JWT_EXPIRES_IN_SECONDS", "900"))        # 15m
JWT_REFRESH_EXPIRES_IN = int(os.getenv("JWT_REFRESH_EXPIRES_IN_SECONDS", "604800"))  # 7d
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "10"))
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:4005")
CORE_API_URL = os.getenv("CORE_API_URL", "http://core:8000")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)

# ─── DB pool ──────────────────────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    return _pool


MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email            TEXT UNIQUE NOT NULL,
    phone            TEXT,
    password_hash    TEXT NOT NULL,
    is_verified      BOOLEAN NOT NULL DEFAULT FALSE,
    totp_secret      TEXT,
    totp_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)
    logger.info("Auth service started on :%d", PORT)
    yield
    await _pool.close()
    logger.info("Auth service stopped")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_token(subject: str, secret: str, expires_in: int, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(seconds=expires_in), **(extra or {})}
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


_bearer = HTTPBearer()


def _get_claims(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    return _decode_token(credentials.credentials, JWT_SECRET)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Auth Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, pool: asyncpg.Pool = Depends(get_pool)):
    existing = await pool.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = pwd_ctx.hash(body.password)
    user_id = await pool.fetchval(
        "INSERT INTO users(email, phone, password_hash) VALUES($1,$2,$3) RETURNING id",
        body.email, body.phone, password_hash,
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/internal/notify",
                json={"userId": str(user_id), "type": "email_verification", "email": body.email},
            )
    except Exception as exc:
        logger.warning("Failed to send verification email: %s", exc)

    return {"success": True, "userId": str(user_id)}


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT id, password_hash, totp_enabled, totp_secret FROM users WHERE email=$1", body.email
    )
    if not row or not pwd_ctx.verify(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if row["totp_enabled"]:
        if not body.totp_code:
            raise HTTPException(status_code=401, detail="TOTP code required")
        import pyotp
        totp = pyotp.TOTP(row["totp_secret"])
        if not totp.verify(body.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid TOTP code")

    user_id = str(row["id"])
    access_token = _make_token(user_id, JWT_SECRET, JWT_EXPIRES_IN)
    refresh_raw = str(uuid.uuid4())
    refresh_hash = pwd_ctx.hash(refresh_raw)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=JWT_REFRESH_EXPIRES_IN)
    await pool.execute(
        "INSERT INTO refresh_tokens(user_id, token_hash, expires_at) VALUES($1,$2,$3)",
        row["id"], refresh_hash, expires_at,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_raw)


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, user_id, token_hash, expires_at FROM refresh_tokens WHERE expires_at > now()"
    )
    matched = next((r for r in rows if pwd_ctx.verify(body.refresh_token, r["token_hash"])), None)
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    await pool.execute("DELETE FROM refresh_tokens WHERE id=$1", matched["id"])
    user_id = str(matched["user_id"])
    access_token = _make_token(user_id, JWT_SECRET, JWT_EXPIRES_IN)
    new_refresh_raw = str(uuid.uuid4())
    new_refresh_hash = pwd_ctx.hash(new_refresh_raw)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=JWT_REFRESH_EXPIRES_IN)
    await pool.execute(
        "INSERT INTO refresh_tokens(user_id, token_hash, expires_at) VALUES($1,$2,$3)",
        matched["user_id"], new_refresh_hash, expires_at,
    )
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_raw)


@app.post("/auth/logout")
async def logout(claims: dict = Depends(_get_claims), pool: asyncpg.Pool = Depends(get_pool)):
    await pool.execute("DELETE FROM refresh_tokens WHERE user_id=$1", uuid.UUID(claims["sub"]))
    return {"success": True}


@app.get("/auth/me")
async def me(claims: dict = Depends(_get_claims), pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT id, email, phone, is_verified, totp_enabled, created_at FROM users WHERE id=$1",
        uuid.UUID(claims["sub"]),
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "phone": row["phone"],
        "isVerified": row["is_verified"],
        "totpEnabled": row["totp_enabled"],
        "createdAt": row["created_at"].isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
