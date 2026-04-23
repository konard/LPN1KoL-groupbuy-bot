import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.requests.models import BuyerRequest
from app.modules.requests.schemas import BuyerRequestCreate, BuyerRequestUpdate


async def create_request(
    db: AsyncSession, req: BuyerRequestCreate, buyer_id: uuid.UUID
) -> BuyerRequest:
    buyer_request = BuyerRequest(
        buyer_id=buyer_id,
        product_name=req.product_name,
        quantity=req.quantity,
        city=req.city,
        notes=req.notes,
    )
    db.add(buyer_request)
    await db.commit()
    await db.refresh(buyer_request)
    return buyer_request


async def list_requests(
    db: AsyncSession,
    buyer_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[BuyerRequest]:
    q = select(BuyerRequest).where(BuyerRequest.is_active.is_(True))
    if buyer_id:
        q = q.where(BuyerRequest.buyer_id == buyer_id)
    result = await db.execute(q.order_by(BuyerRequest.created_at.desc()).offset(skip).limit(limit))
    return list(result.scalars().all())


async def get_request(db: AsyncSession, request_id: uuid.UUID) -> BuyerRequest | None:
    return await db.get(BuyerRequest, request_id)


async def update_request(
    db: AsyncSession,
    request_id: uuid.UUID,
    req: BuyerRequestUpdate,
    buyer_id: uuid.UUID,
) -> BuyerRequest:
    buyer_request = await db.get(BuyerRequest, request_id)
    if not buyer_request or not buyer_request.is_active:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if buyer_request.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Нет прав для редактирования этого запроса")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(buyer_request, field, value)
    await db.commit()
    await db.refresh(buyer_request)
    return buyer_request


async def delete_request(
    db: AsyncSession, request_id: uuid.UUID, buyer_id: uuid.UUID
) -> dict:
    buyer_request = await db.get(BuyerRequest, request_id)
    if not buyer_request or not buyer_request.is_active:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if buyer_request.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Нет прав для удаления этого запроса")
    buyer_request.is_active = False
    await db.commit()
    return {"detail": "Запрос удалён"}
