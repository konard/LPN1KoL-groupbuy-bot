import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka_producer import publish
from app.modules.payment.models import Escrow, Wallet


async def get_or_create_wallet(db: AsyncSession, user_id: uuid.UUID) -> Wallet:
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id))
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
    return wallet


async def deposit(db: AsyncSession, user_id: uuid.UUID, amount: Decimal) -> Wallet:
    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance += amount
    await db.commit()
    await db.refresh(wallet)
    await publish(
        "monolith.payment.deposited", {"user_id": str(user_id), "amount": str(amount)}
    )
    return wallet


async def hold(db: AsyncSession, user_id: uuid.UUID, amount: Decimal) -> Wallet:
    from fastapi import HTTPException

    wallet = await get_or_create_wallet(db, user_id)
    available = wallet.balance - wallet.hold_amount
    if available < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    wallet.hold_amount += amount
    await db.commit()
    await db.refresh(wallet)
    return wallet


async def create_escrow(
    db: AsyncSession, payer_id: uuid.UUID, purchase_id: uuid.UUID, amount: Decimal
) -> Escrow:
    escrow = Escrow(purchase_id=purchase_id, payer_id=payer_id, amount=amount)
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    await publish(
        "monolith.payment.escrow_created",
        {
            "escrow_id": str(escrow.id),
            "purchase_id": str(purchase_id),
            "amount": str(amount),
        },
    )
    return escrow


async def release_escrow(db: AsyncSession, escrow_id: uuid.UUID) -> Escrow:
    from fastapi import HTTPException

    escrow = await db.get(Escrow, escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    escrow.status = "released"
    await db.commit()
    await db.refresh(escrow)
    await publish(
        "monolith.payment.success",
        {"escrow_id": str(escrow_id), "purchase_id": str(escrow.purchase_id)},
    )
    return escrow
