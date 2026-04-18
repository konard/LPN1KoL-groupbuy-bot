import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.reputation import schemas, service

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.post("/reviews", response_model=schemas.ReviewOut, status_code=201)
async def create_review(
    req: schemas.ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_review(db, req, current_user.id)


@router.get("/reviews/{target_id}", response_model=list[schemas.ReviewOut])
async def list_reviews(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await service.list_reviews(db, target_id)


@router.get("/ratings/{target_id}")
async def get_rating(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await service.get_rating(db, target_id)
