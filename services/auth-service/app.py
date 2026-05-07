"""
Auth service — Python/FastAPI implementation of the phone + email OTP flow.

Endpoints implemented:
    POST /register            (start registration: phone + email → OTP to email)
    POST /register/confirm    (verify OTP → create user → return tokens)
    POST /login               (start login by phone → OTP to user's email)
    POST /login/confirm       (verify OTP → return tokens)
    POST /resend-code         (resend OTP for an active session)
    POST /refresh             (rotate refresh token)
    POST /logout              (blacklist access token + clear refresh)
    GET  /validate            (validate Bearer token)
    GET  /me                  (current user profile)
    GET  /health              (health check)

The OTP delivery is dispatched via notification-service POST /internal/send-otp.
Pending sessions and OTP codes are kept in Redis with short TTLs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Literal

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, EmailStr

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auth-service")

PORT = int(os.getenv("PORT", "4001"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/auth_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "change_me_refresh")
JWT_EXPIRES_IN = int(os.getenv("JWT_EXPIRES_IN_SECONDS", "900"))            # 15m
JWT_REFRESH_EXPIRES_IN = int(os.getenv("JWT_REFRESH_EXPIRES_IN_SECONDS", "604800"))  # 7d
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "10"))
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:4005")
CORE_API_URL = os.getenv("CORE_API_URL", "http://core:8000")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

OTP_TTL_SECONDS = 600        # 10 minutes
OTP_RESEND_COOLDOWN = 30     # seconds
OTP_LENGTH = 6
PHONE_RE = re.compile(r"^\+?[1-9]\d{6,19}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)


# ─── Resources ────────────────────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None


async def get_pool() -> asyncpg.Pool:
    assert _pool is not None
    return _pool


async def get_redis() -> aioredis.Redis | None:
    return _redis


MIGRATIONS = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator', 'organizer', 'supplier', 'buyer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone               VARCHAR(20) UNIQUE NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    first_name          VARCHAR(100),
    last_name           VARCHAR(100),
    role                user_role NOT NULL DEFAULT 'user',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    refresh_token_hash  TEXT,
    last_login_at       TIMESTAMPTZ,
    is_banned           BOOLEAN NOT NULL DEFAULT FALSE,
    banned_at           TIMESTAMPTZ,
    ban_reason          TEXT,
    two_factor_secret   VARCHAR(255),
    two_factor_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    backup_codes        TEXT,
    two_factor_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _redis
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)
    try:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis ready at %s", REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s); OTP sessions will use in-memory fallback", exc)
        _redis = None
    logger.info("Auth service started on :%d", PORT)
    yield
    await _pool.close()
    if _redis is not None:
        await _redis.aclose()
    logger.info("Auth service stopped")


# ─── In-memory fallback when Redis is unavailable (single-instance only) ──────

_memstore: dict[str, tuple[str, datetime]] = {}


async def kv_set(key: str, value: str, ttl: int) -> None:
    if _redis is not None:
        await _redis.set(key, value, ex=ttl)
        return
    _memstore[key] = (value, datetime.now(timezone.utc) + timedelta(seconds=ttl))


async def kv_get(key: str) -> str | None:
    if _redis is not None:
        return await _redis.get(key)
    entry = _memstore.get(key)
    if not entry:
        return None
    value, exp = entry
    if datetime.now(timezone.utc) > exp:
        _memstore.pop(key, None)
        return None
    return value


async def kv_del(key: str) -> None:
    if _redis is not None:
        await _redis.delete(key)
        return
    _memstore.pop(key, None)


# ─── Token helpers ────────────────────────────────────────────────────────────

def _make_token(payload: dict, secret: str, expires_in: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


_bearer = HTTPBearer(auto_error=False)


async def _get_claims(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="No token provided")
    payload = _decode_token(creds.credentials, JWT_SECRET)
    blacklisted = await kv_get(f"jwt:blacklist:{creds.credentials}")
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token revoked")
    return payload


def _generate_otp(length: int = OTP_LENGTH) -> str:
    low = 10 ** (length - 1)
    high = 10 ** length
    return str(secrets.randbelow(high - low) + low)


def _mask_email(email: str) -> str:
    at = email.find("@")
    if at < 0:
        return "***"
    local, domain = email[:at], email[at + 1:]
    dot = domain.rfind(".")
    name, tld = (domain[:dot], domain[dot:]) if dot > 0 else (domain, "")
    masked_local = (local[0] + "***") if len(local) > 1 else "***"
    masked_domain = (name[0] + "***") if len(name) > 1 else "***"
    return f"{masked_local}@{masked_domain}{tld}"


async def _send_otp_email(email: str, otp: str, context: Literal["login", "registration"]) -> None:
    """Dispatch the OTP through notification-service. Non-fatal on failure."""
    subject = (
        "Groupbuy — код подтверждения регистрации"
        if context == "registration"
        else "Groupbuy — код для входа"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/internal/send-otp",
                json={"email": email, "otp": otp, "subject": subject, "context": context},
            )
    except Exception as exc:
        logger.warning("Failed to send OTP email to %s: %s", email, exc)


async def _sync_user_to_core(user: dict) -> None:
    """Best-effort sync to core API so /api/users/by_email/ resolves."""
    body = {
        "platform": "websocket",
        "platform_user_id": str(user["id"]),
        "username": user["email"],
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "phone": user.get("phone") or "",
        "email": user["email"],
        "role": user.get("role") or "buyer",
        "language_code": "ru",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{CORE_API_URL}/api/users/", json=body)
    except Exception as exc:
        logger.warning("CoreSync failed for %s: %s", user["email"], exc)


def _validate_phone(phone: str) -> None:
    if not phone or not PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number format")


def _validate_email(email: str) -> None:
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")


async def _generate_tokens(user_id: str, email: str, role: str) -> dict:
    jti = str(uuid.uuid4())
    access = _make_token(
        {"sub": user_id, "email": email, "role": role, "jti": jti},
        JWT_SECRET,
        JWT_EXPIRES_IN,
    )
    refresh = _make_token(
        {"sub": user_id, "email": email, "role": role, "jti": str(uuid.uuid4())},
        JWT_REFRESH_SECRET,
        JWT_REFRESH_EXPIRES_IN,
    )
    refresh_hash = pwd_ctx.hash(refresh)
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET refresh_token_hash=$1, last_login_at=NOW() WHERE id=$2",
        refresh_hash, uuid.UUID(user_id),
    )
    return {"accessToken": access, "refreshToken": refresh, "expiresIn": JWT_EXPIRES_IN}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str
    email: str
    firstName: str | None = None
    lastName: str | None = None
    role: str | None = None


class ConfirmRegistrationRequest(BaseModel):
    phone: str
    otp: str = Field(min_length=4, max_length=8)


class LoginRequest(BaseModel):
    phone: str


class ConfirmLoginRequest(BaseModel):
    phone: str
    otp: str = Field(min_length=4, max_length=8)


class ResendOtpRequest(BaseModel):
    phone: str
    context: Literal["login", "registration"]


class RefreshRequest(BaseModel):
    refreshToken: str


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Auth Service", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}


# ─── Registration: phone + email → OTP → confirm ──────────────────────────────

@app.post("/register", status_code=status.HTTP_200_OK)
async def register(body: RegisterRequest):
    _validate_phone(body.phone)
    _validate_email(body.email)
    pool = await get_pool()

    existing_phone = await pool.fetchrow("SELECT id FROM users WHERE phone=$1", body.phone)
    if existing_phone:
        raise HTTPException(status_code=400, detail="User with this phone number already exists")
    existing_email = await pool.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    otp = _generate_otp()
    pending = {
        "phone": body.phone,
        "email": body.email,
        "firstName": body.firstName,
        "lastName": body.lastName,
        "role": body.role,
        "otp": otp,
    }
    await kv_set(f"reg:pending:{body.phone}", json.dumps(pending), OTP_TTL_SECONDS)
    await _send_otp_email(body.email, otp, "registration")

    return {
        "success": True,
        "data": {
            "otpSent": True,
            "message": "Verification code sent to your email",
            "maskedEmail": _mask_email(body.email),
        },
    }


@app.post("/register/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_registration(body: ConfirmRegistrationRequest):
    _validate_phone(body.phone)
    raw = await kv_get(f"reg:pending:{body.phone}")
    if not raw:
        raise HTTPException(status_code=400, detail="Registration session expired or not found. Please start over.")

    try:
        pending = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid registration session data")

    if pending.get("otp") != body.otp.strip():
        raise HTTPException(status_code=401, detail="Invalid verification code")

    await kv_del(f"reg:pending:{body.phone}")

    pool = await get_pool()
    role = pending.get("role") or "user"
    row = await pool.fetchrow(
        """
        INSERT INTO users(phone, email, first_name, last_name, role, is_email_verified)
        VALUES($1, $2, $3, $4, $5::user_role, TRUE)
        RETURNING id, phone, email, first_name, last_name, role
        """,
        pending["phone"], pending["email"],
        pending.get("firstName"), pending.get("lastName"), role,
    )
    user = {
        "id": row["id"],
        "phone": row["phone"],
        "email": row["email"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "role": row["role"],
    }
    asyncio.create_task(_sync_user_to_core(user))

    tokens = await _generate_tokens(str(row["id"]), row["email"], row["role"])
    return {"success": True, "data": tokens}


# ─── Login: phone → OTP → confirm ─────────────────────────────────────────────

@app.post("/login", status_code=status.HTTP_200_OK)
async def login(body: LoginRequest):
    _validate_phone(body.phone)
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, role, is_active, is_banned FROM users WHERE phone=$1",
        body.phone,
    )

    if not row:
        # Anti-enumeration: same response when phone is unknown.
        return {
            "success": True,
            "data": {
                "otpSent": True,
                "message": "If this number is registered, a code will be sent to the associated email",
            },
        }

    if not row["is_active"]:
        raise HTTPException(status_code=401, detail="Account is disabled")
    if row["is_banned"]:
        raise HTTPException(
            status_code=403,
            detail={"status": 403, "code": "USER_BANNED", "message": "Your account has been suspended"},
        )

    otp = _generate_otp()
    await kv_set(
        f"login:otp:{body.phone}",
        json.dumps({"userId": str(row["id"]), "otp": otp}),
        OTP_TTL_SECONDS,
    )
    await _send_otp_email(row["email"], otp, "login")

    return {
        "success": True,
        "data": {
            "otpSent": True,
            "message": "If this number is registered, a code will be sent to the associated email",
            "maskedEmail": _mask_email(row["email"]),
        },
    }


@app.post("/login/confirm", status_code=status.HTTP_200_OK)
async def confirm_login(body: ConfirmLoginRequest):
    _validate_phone(body.phone)
    raw = await kv_get(f"login:otp:{body.phone}")
    if not raw:
        raise HTTPException(
            status_code=401,
            detail="Verification code expired or not found. Please request a new code.",
        )
    try:
        session = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid login session")

    if session.get("otp") != body.otp.strip():
        raise HTTPException(status_code=401, detail="Invalid verification code")

    await kv_del(f"login:otp:{body.phone}")

    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, role, is_active, is_banned FROM users WHERE id=$1",
        uuid.UUID(session["userId"]),
    )
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    if not row["is_active"]:
        raise HTTPException(status_code=401, detail="Account is disabled")
    if row["is_banned"]:
        raise HTTPException(
            status_code=403,
            detail={"status": 403, "code": "USER_BANNED", "message": "Your account has been suspended"},
        )

    tokens = await _generate_tokens(str(row["id"]), row["email"], row["role"])
    return {"success": True, "data": {"requires2FA": False, **tokens}}


# ─── Resend OTP ───────────────────────────────────────────────────────────────

@app.post("/resend-code", status_code=status.HTTP_200_OK)
async def resend_code(body: ResendOtpRequest):
    _validate_phone(body.phone)
    cooldown_key = f"otp:resend:cooldown:{body.context}:{body.phone}"
    if await kv_get(cooldown_key):
        raise HTTPException(
            status_code=400,
            detail=f"Please wait {OTP_RESEND_COOLDOWN} seconds before requesting a new code",
        )

    otp = _generate_otp()

    if body.context == "login":
        raw = await kv_get(f"login:otp:{body.phone}")
        if not raw:
            return {
                "success": True,
                "data": {
                    "otpSent": True,
                    "message": "If this number is registered, a new code will be sent to the associated email",
                },
            }
        try:
            session = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid login session")

        pool = await get_pool()
        user = await pool.fetchrow(
            "SELECT id, email FROM users WHERE id=$1",
            uuid.UUID(session["userId"]),
        )
        if not user:
            return {
                "success": True,
                "data": {
                    "otpSent": True,
                    "message": "If this number is registered, a new code will be sent to the associated email",
                },
            }

        await kv_set(
            f"login:otp:{body.phone}",
            json.dumps({"userId": str(user["id"]), "otp": otp}),
            OTP_TTL_SECONDS,
        )
        await _send_otp_email(user["email"], otp, "login")

    else:  # registration
        raw = await kv_get(f"reg:pending:{body.phone}")
        if not raw:
            raise HTTPException(
                status_code=400,
                detail="Registration session expired or not found. Please start over.",
            )
        try:
            pending = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid registration session data")

        pending["otp"] = otp
        await kv_set(f"reg:pending:{body.phone}", json.dumps(pending), OTP_TTL_SECONDS)
        await _send_otp_email(pending["email"], otp, "registration")

    await kv_set(cooldown_key, "1", OTP_RESEND_COOLDOWN)

    return {
        "success": True,
        "data": {"otpSent": True, "message": "A new verification code has been sent"},
    }


# ─── Token management ─────────────────────────────────────────────────────────

@app.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(body: RefreshRequest):
    payload = _decode_token(body.refreshToken, JWT_REFRESH_SECRET)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, role, refresh_token_hash, is_active, is_banned FROM users WHERE id=$1",
        uuid.UUID(user_id),
    )
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    if not row["refresh_token_hash"] or not pwd_ctx.verify(body.refreshToken, row["refresh_token_hash"]):
        raise HTTPException(status_code=401, detail="Refresh token mismatch")
    if not row["is_active"]:
        raise HTTPException(status_code=401, detail="Account is disabled")

    # Rotate
    await pool.execute("UPDATE users SET refresh_token_hash=NULL WHERE id=$1", row["id"])
    tokens = await _generate_tokens(str(row["id"]), row["email"], row["role"])
    return {"success": True, "data": tokens}


@app.post("/logout", status_code=status.HTTP_200_OK)
async def logout(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="No token provided")
    payload = _decode_token(creds.credentials, JWT_SECRET)
    await kv_set(f"jwt:blacklist:{creds.credentials}", "1", JWT_EXPIRES_IN)
    pool = await get_pool()
    await pool.execute("UPDATE users SET refresh_token_hash=NULL WHERE id=$1", uuid.UUID(payload["sub"]))
    return {"success": True, "message": "Logged out successfully"}


@app.get("/validate", status_code=status.HTTP_200_OK)
async def validate(claims: dict = Depends(_get_claims)):
    return {"success": True, "data": claims}


@app.get("/me", status_code=status.HTTP_200_OK)
async def me(claims: dict = Depends(_get_claims)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, phone, email, first_name, last_name, role,
               is_active, is_email_verified, two_factor_enabled, created_at
        FROM users WHERE id=$1
        """,
        uuid.UUID(claims["sub"]),
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "success": True,
        "data": {
            "id": str(row["id"]),
            "phone": row["phone"],
            "email": row["email"],
            "firstName": row["first_name"],
            "lastName": row["last_name"],
            "role": row["role"],
            "isActive": row["is_active"],
            "isEmailVerified": row["is_email_verified"],
            "twoFactorEnabled": row["two_factor_enabled"],
            "createdAt": row["created_at"].isoformat(),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
