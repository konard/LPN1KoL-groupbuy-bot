import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka_producer import publish
from app.modules.purchase.models import Purchase, Vote
from app.modules.purchase.schemas import PurchaseCreate, VoteCreate


async def create_purchase(
    db: AsyncSession, req: PurchaseCreate, organizer_id: uuid.UUID
) -> Purchase:
    purchase = Purchase(
        title=req.title,
        description=req.description,
        organizer_id=organizer_id,
        target_amount=req.target_amount,
        commission_pct=req.commission_pct,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    await publish(
        "monolith.purchase.created",
        {"purchase_id": str(purchase.id), "organizer_id": str(organizer_id)},
    )
    return purchase


async def get_purchase(db: AsyncSession, purchase_id: uuid.UUID) -> Purchase | None:
    return await db.get(Purchase, purchase_id)


async def list_purchases(
    db: AsyncSession, skip: int = 0, limit: int = 20
) -> list[Purchase]:
    result = await db.execute(select(Purchase).offset(skip).limit(limit))
    return list(result.scalars().all())


async def cast_vote(
    db: AsyncSession, purchase_id: uuid.UUID, user_id: uuid.UUID, req: VoteCreate
) -> Vote:
    from fastapi import HTTPException

    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    vote = Vote(purchase_id=purchase_id, user_id=user_id, value=req.value)
    db.add(vote)
    await db.commit()
    await db.refresh(vote)
    return vote
