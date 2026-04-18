import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.payment import schemas, service

router = APIRouter(prefix="/wallets", tags=["wallets"])
escrow_router = APIRouter(prefix="/escrow", tags=["escrow"])


@router.get("/me", response_model=schemas.WalletOut)
async def my_wallet(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await service.get_or_create_wallet(db, current_user.id)


@router.post("/me/deposit", response_model=schemas.WalletOut)
async def deposit(
    req: schemas.DepositRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.deposit(db, current_user.id, req.amount)


@router.post("/me/hold", response_model=schemas.WalletOut)
async def hold(
    req: schemas.HoldRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.hold(db, current_user.id, req.amount)


@escrow_router.post("", response_model=schemas.EscrowOut, status_code=201)
async def create_escrow(
    req: schemas.EscrowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_escrow(db, current_user.id, req.purchase_id, req.amount)


@escrow_router.post("/{escrow_id}/release", response_model=schemas.EscrowOut)
async def release_escrow(
    escrow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await service.release_escrow(db, escrow_id)
