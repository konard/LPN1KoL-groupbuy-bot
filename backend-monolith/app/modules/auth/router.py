import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth import schemas, service
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
async def register(req: schemas.RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await service.register_user(db, req)


@router.post("/login", response_model=schemas.TokenResponse)
async def login(req: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    return await service.login_user(db, req)


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh(req: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    from jose import JWTError

    try:
        payload = service.decode_token(req.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return service.create_token_pair(user.id, user.email)


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
