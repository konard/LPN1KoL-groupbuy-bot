import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.purchase import schemas, service

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", response_model=schemas.PurchaseOut, status_code=201)
async def create_purchase(
    req: schemas.PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_purchase(db, req, current_user.id)


@router.get("", response_model=list[schemas.PurchaseOut])
async def list_purchases(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await service.list_purchases(db, skip, limit)


@router.get("/{purchase_id}", response_model=schemas.PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from fastapi import HTTPException

    p = await service.get_purchase(db, purchase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return p


@router.post("/{purchase_id}/vote", response_model=schemas.VoteOut, status_code=201)
async def vote(
    purchase_id: uuid.UUID,
    req: schemas.VoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.cast_vote(db, purchase_id, current_user.id, req)
