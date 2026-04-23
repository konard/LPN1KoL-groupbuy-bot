import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka_producer import publish
from app.modules.purchase.models import Category, Participant, Purchase, Vote
from app.modules.purchase.schemas import (
    CategoryCreate,
    JoinPurchaseRequest,
    PurchaseCreate,
    VoteCreate,
)

# ── Category ──────────────────────────────────────────────────────────────────


async def list_categories(
    db: AsyncSession, parent_id: uuid.UUID | None = None, include_inactive: bool = False
) -> list[Category]:
    q = select(Category)
    if not include_inactive:
        q = q.where(Category.is_active.is_(True))
    if parent_id is not None:
        q = q.where(Category.parent_id == parent_id)
    else:
        q = q.where(Category.parent_id.is_(None))
    result = await db.execute(q.order_by(Category.name))
    return list(result.scalars().all())


async def create_category(db: AsyncSession, req: CategoryCreate) -> Category:
    cat = Category(
        name=req.name,
        description=req.description,
        parent_id=req.parent_id,
        icon=req.icon,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def get_category(db: AsyncSession, category_id: uuid.UUID) -> Category | None:
    return await db.get(Category, category_id)


# ── Purchase / Procurement ────────────────────────────────────────────────────

VALID_STATUSES = {"draft", "active", "stopped", "payment", "completed", "cancelled"}


async def create_purchase(
    db: AsyncSession, req: PurchaseCreate, organizer_id: uuid.UUID
) -> Purchase:
    purchase = Purchase(
        title=req.title,
        description=req.description,
        organizer_id=organizer_id,
        target_amount=req.target_amount,
        commission_pct=req.commission_pct,
        category_id=req.category_id,
        city=req.city,
        delivery_address=req.delivery_address,
        stop_at_amount=req.stop_at_amount,
        unit=req.unit,
        price_per_unit=req.price_per_unit,
        min_quantity=req.min_quantity,
        deadline=req.deadline,
        image_url=req.image_url,
        status="active",
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
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    city: str | None = None,
    category_id: uuid.UUID | None = None,
    organizer_id: uuid.UUID | None = None,
    active_only: bool = False,
) -> list[Purchase]:
    q = select(Purchase)
    if status:
        q = q.where(Purchase.status == status)
    if active_only:
        q = q.where(Purchase.status == "active")
    if city:
        q = q.where(Purchase.city.ilike(f"%{city}%"))
    if category_id:
        q = q.where(Purchase.category_id == category_id)
    if organizer_id:
        q = q.where(Purchase.organizer_id == organizer_id)
    result = await db.execute(q.order_by(Purchase.created_at.desc()).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_status(
    db: AsyncSession, purchase_id: uuid.UUID, new_status: str, organizer_id: uuid.UUID
) -> Purchase:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.organizer_id != organizer_id:
        raise HTTPException(status_code=403, detail="Only organizer can update status")
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    purchase.status = new_status
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def close_purchase(
    db: AsyncSession, purchase_id: uuid.UUID, organizer_id: uuid.UUID
) -> Purchase:
    return await update_status(db, purchase_id, "completed", organizer_id)


async def approve_supplier(
    db: AsyncSession,
    purchase_id: uuid.UUID,
    supplier_id: uuid.UUID,
    organizer_id: uuid.UUID,
) -> Purchase:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.organizer_id != organizer_id:
        raise HTTPException(status_code=403, detail="Only organizer can approve supplier")
    purchase.supplier_id = supplier_id
    purchase.status = "payment"
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def stop_amount(
    db: AsyncSession, purchase_id: uuid.UUID, organizer_id: uuid.UUID
) -> Purchase:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.organizer_id != organizer_id:
        raise HTTPException(status_code=403, detail="Only organizer can trigger stop-amount")
    purchase.status = "stopped"
    await db.commit()
    await db.refresh(purchase)
    return purchase


# ── Participants ──────────────────────────────────────────────────────────────


async def list_participants(
    db: AsyncSession, purchase_id: uuid.UUID
) -> list[Participant]:
    result = await db.execute(
        select(Participant).where(
            Participant.purchase_id == purchase_id, Participant.is_active.is_(True)
        )
    )
    return list(result.scalars().all())


async def join_purchase(
    db: AsyncSession,
    purchase_id: uuid.UUID,
    user_id: uuid.UUID,
    req: JoinPurchaseRequest,
) -> Participant:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.status != "active":
        raise HTTPException(status_code=400, detail="Cannot join this purchase")

    existing = await db.scalar(
        select(Participant).where(
            Participant.purchase_id == purchase_id,
            Participant.user_id == user_id,
            Participant.is_active.is_(True),
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already participating")

    participant = Participant(
        purchase_id=purchase_id,
        user_id=user_id,
        quantity=req.quantity,
        amount=req.amount,
        city=req.city,
        notes=req.notes,
        status="pending",
    )
    db.add(participant)

    # Update current_amount
    purchase.current_amount += req.amount
    if purchase.stop_at_amount and purchase.current_amount >= purchase.stop_at_amount:
        purchase.status = "stopped"

    await db.commit()
    await db.refresh(participant)
    return participant


async def leave_purchase(
    db: AsyncSession, purchase_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    participant = await db.scalar(
        select(Participant).where(
            Participant.purchase_id == purchase_id,
            Participant.user_id == user_id,
            Participant.is_active.is_(True),
        )
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Not participating")

    participant.is_active = False
    participant.status = "cancelled"
    purchase.current_amount = max(Decimal("0"), purchase.current_amount - participant.amount)
    await db.commit()
    return {"detail": "Left successfully"}


# ── Votes / Supplier selection ────────────────────────────────────────────────


async def cast_vote(
    db: AsyncSession, purchase_id: uuid.UUID, user_id: uuid.UUID, req: VoteCreate
) -> Vote:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    vote = Vote(
        purchase_id=purchase_id,
        user_id=user_id,
        value=req.value,
        candidate_id=req.candidate_id,
    )
    db.add(vote)
    await db.commit()
    await db.refresh(vote)
    return vote


async def get_vote_results(db: AsyncSession, purchase_id: uuid.UUID) -> list[dict]:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    result = await db.execute(
        select(
            Vote.candidate_id,
            func.count(Vote.id).label("total_votes"),
            func.sum(Vote.value).label("total_value"),
        )
        .where(Vote.purchase_id == purchase_id)
        .group_by(Vote.candidate_id)
        .order_by(func.sum(Vote.value).desc())
    )
    rows = result.all()
    return [
        {
            "candidate_id": row.candidate_id,
            "total_votes": row.total_votes,
            "total_value": row.total_value or 0,
        }
        for row in rows
    ]


# ── Receipt table ─────────────────────────────────────────────────────────────


async def get_receipt_table(db: AsyncSession, purchase_id: uuid.UUID) -> dict:
    purchase = await db.get(Purchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    participants = await list_participants(db, purchase_id)
    rows = [
        {
            "user_id": str(p.user_id),
            "quantity": str(p.quantity),
            "amount": str(p.amount),
            "status": p.status,
        }
        for p in participants
    ]
    return {
        "purchase_id": str(purchase_id),
        "title": purchase.title,
        "total_amount": str(purchase.current_amount),
        "participants": rows,
    }
