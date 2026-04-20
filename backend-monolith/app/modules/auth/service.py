import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_token_pair(
    user_id: uuid.UUID, email: str, role: str = "user"
) -> TokenResponse:
    access = _create_token(
        {"sub": str(user_id), "email": email, "role": role},
        timedelta(minutes=settings.jwt_expires_minutes),
    )
    refresh = _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.jwt_refresh_expires_days),
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def register_user(db: AsyncSession, req: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == req.email))
    if existing:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=req.email,
        password_hash=_hash_password(req.password),
        platform=req.platform,
        platform_user_id=req.platform_user_id,
        username=req.username,
        first_name=req.first_name,
        last_name=req.last_name,
        phone=req.phone,
        role=req.role,
        language_code=req.language_code,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, req: LoginRequest) -> TokenResponse:
    from fastapi import HTTPException

    user = await db.scalar(select(User).where(User.email == req.email))
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.totp_enabled:
        if not req.totp_code:
            raise HTTPException(status_code=401, detail="TOTP code required")
        if not pyotp.TOTP(user.totp_secret).verify(req.totp_code):
            raise HTTPException(status_code=401, detail="Invalid TOTP code")
    return create_token_pair(user.id, user.email, user.role)


async def setup_totp(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    user = await db.get(User, user_id)
    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="GroupBuy")
    return secret, uri


async def verify_and_enable_totp(
    db: AsyncSession, user_id: uuid.UUID, code: str
) -> bool:
    from fastapi import HTTPException

    user = await db.get(User, user_id)
    if not user or not user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not set up")
    if not pyotp.TOTP(user.totp_secret).verify(code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    user.totp_enabled = True
    await db.commit()
    return True
