import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from jose import jwt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.modules.auth import schemas, service
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

# ── Auth endpoints ────────────────────────────────────────────────────────────


@router.post("/register", response_model=schemas.UserOut, status_code=201)
async def register(req: schemas.RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await service.register_user(db, req)


@router.post("/login", response_model=schemas.TokenResponse)
async def login(req: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    return await service.login_user(db, req)


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh(req: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = service.decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return service.create_token_pair(user.id, user.email, user.role)


@router.post("/2fa/setup", response_model=schemas.TOTPSetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    secret, uri = await service.setup_totp(db, current_user.id)
    return schemas.TOTPSetupResponse(secret=secret, qr_uri=uri)


@router.post("/2fa/verify")
async def verify_2fa(
    req: schemas.TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.verify_and_enable_totp(db, current_user.id, req.code)
    return {"detail": "2FA enabled"}


@router.get("/me", response_model=schemas.UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# ── User management endpoints ─────────────────────────────────────────────────


@users_router.get("", response_model=list[schemas.UserOut])
async def list_users(
    role: str | None = Query(None),
    platform: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List users with optional filters by role and platform."""
    q = select(User)
    if role:
        q = q.where(User.role == role)
    if platform:
        q = q.where(User.platform == platform)
    result = await db.execute(q.offset(skip).limit(limit))
    return list(result.scalars().all())


@users_router.get("/by_platform", response_model=schemas.UserOut)
async def get_user_by_platform(
    platform: str = Query("telegram"),
    platform_user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get user by platform and platform_user_id."""
    user = await db.scalar(
        select(User).where(
            User.platform == platform, User.platform_user_id == platform_user_id
        )
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.get("/by_email", response_model=schemas.UserOut)
async def get_user_by_email(
    email: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get user by email address."""
    user = await db.scalar(select(User).where(User.email.ilike(email)))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.get("/by_phone", response_model=schemas.UserOut)
async def get_user_by_phone(
    phone: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get user by phone number."""
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    user = await db.scalar(select(User).where(User.phone == phone))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.get("/check_exists")
async def check_user_exists(
    platform: str = Query("telegram"),
    platform_user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Check whether a user with given platform credentials exists."""
    exists = await db.scalar(
        select(User).where(
            User.platform == platform, User.platform_user_id == platform_user_id
        )
    )
    return {"exists": exists is not None}


@users_router.get("/search", response_model=list[schemas.UserOut])
async def search_users(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Search users by name, username, email, or phone."""
    pattern = f"%{q}%"
    result = await db.execute(
        select(User)
        .where(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )
        .limit(20)
    )
    return list(result.scalars().all())


@users_router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single user by ID."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.patch("/{user_id}", response_model=schemas.UserOut)
async def update_user(
    user_id: uuid.UUID,
    req: schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Update user profile fields."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@users_router.get("/{user_id}/balance", response_model=schemas.UserBalanceOut)
async def get_user_balance(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get user balance with deposit/spent statistics."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from decimal import Decimal

    from sqlalchemy import text

    row = await db.execute(
        text("SELECT balance, hold_amount FROM payment.wallets WHERE user_id = :uid"),
        {"uid": user_id},
    )
    wallet_row = row.fetchone()
    balance = Decimal(wallet_row[0]) if wallet_row else user.balance
    hold = Decimal(wallet_row[1]) if wallet_row else Decimal("0")

    return schemas.UserBalanceOut(
        balance=balance,
        total_deposited=balance,
        total_spent=hold,
        available=balance - hold,
    )


@users_router.post("/{user_id}/update_balance", response_model=schemas.UserOut)
async def update_user_balance(
    user_id: uuid.UUID,
    req: schemas.UpdateBalanceRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Adjust user balance (positive = credit, negative = debit)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.balance += req.amount
    await db.commit()
    await db.refresh(user)
    return user


@users_router.get("/{user_id}/role")
async def get_user_role(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get the role of a user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"role": user.role}


@users_router.get("/{user_id}/ws_token", response_model=schemas.WsTokenResponse)
async def get_ws_token(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Generate a short-lived WebSocket authentication token (24 h)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ttl = 86400
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "type": "ws",
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return schemas.WsTokenResponse(token=token, expires_in=ttl)
