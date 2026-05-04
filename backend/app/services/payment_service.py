"""
Бизнес-логика платёжного модуля: пополнение, заморозка, эскроу, транзакции.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.clients.kafka_client import publish
from app.models.payment import (
    CommissionModel, EscrowAccountModel, TransactionModel, WalletModel,
)

logger = logging.getLogger(__name__)


def _get_or_create_wallet(db: Session, user_id: int) -> WalletModel:
    """Возвращает кошелёк пользователя. Создаёт автоматически при первом обращении."""
    wallet = db.query(WalletModel).filter(WalletModel.user_id == user_id).first()
    if not wallet:
        wallet = WalletModel(user_id=user_id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def get_wallet(db: Session, user_id: int) -> WalletModel:
    """Возвращает кошелёк, создаёт если не существует."""
    return _get_or_create_wallet(db, user_id)


async def top_up(db: Session, user_id: int, amount: float, description: str = "") -> TransactionModel:
    """Пополняет кошелёк пользователя."""
    wallet = _get_or_create_wallet(db, user_id)
    wallet.balance = Decimal(str(wallet.balance)) + Decimal(str(amount))
    wallet.updated_at = datetime.now(timezone.utc)

    tx = TransactionModel(
        wallet_id=wallet.id,
        type="top_up",
        amount=amount,
        status="completed",
        description=description,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    await publish("payment.topup.completed", {
        "userId": user_id, "amount": amount,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return tx


async def hold_funds(db: Session, user_id: int, amount: float, purchase_id: int,
                     description: str = "") -> TransactionModel:
    """Замораживает средства под закупку (перемещает balance → on_hold)."""
    wallet = _get_or_create_wallet(db, user_id)
    if Decimal(str(wallet.balance)) < Decimal(str(amount)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно средств")
    if wallet.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Кошелёк заморожен")

    wallet.balance = Decimal(str(wallet.balance)) - Decimal(str(amount))
    wallet.on_hold = Decimal(str(wallet.on_hold)) + Decimal(str(amount))
    wallet.updated_at = datetime.now(timezone.utc)

    tx = TransactionModel(
        wallet_id=wallet.id,
        type="hold",
        amount=amount,
        status="completed",
        reference_id=str(purchase_id),
        description=description,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    await publish("payment.hold.created", {
        "userId": user_id, "purchaseId": purchase_id, "amount": amount,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return tx


async def release_funds(db: Session, user_id: int, amount: float, purchase_id: int,
                        description: str = "") -> TransactionModel:
    """Размораживает средства (on_hold → balance)."""
    wallet = _get_or_create_wallet(db, user_id)
    release_amount = min(Decimal(str(amount)), Decimal(str(wallet.on_hold)))
    wallet.on_hold = Decimal(str(wallet.on_hold)) - release_amount
    wallet.balance = Decimal(str(wallet.balance)) + release_amount
    wallet.updated_at = datetime.now(timezone.utc)

    tx = TransactionModel(
        wallet_id=wallet.id,
        type="release",
        amount=float(release_amount),
        status="completed",
        reference_id=str(purchase_id),
        description=description,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    await publish("payment.released", {
        "userId": user_id, "purchaseId": purchase_id, "amount": float(release_amount),
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return tx


async def deposit_escrow(db: Session, purchase_id: int, amount: float) -> EscrowAccountModel:
    """Добавляет средства на эскроу-счёт закупки."""
    escrow = db.query(EscrowAccountModel).filter(EscrowAccountModel.purchase_id == purchase_id).first()
    if not escrow:
        escrow = EscrowAccountModel(purchase_id=purchase_id)
        db.add(escrow)

    escrow.total_deposited = Decimal(str(escrow.total_deposited)) + Decimal(str(amount))
    escrow.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(escrow)
    return escrow


def list_transactions(db: Session, user_id: int, skip: int = 0, limit: int = 50):
    """Возвращает историю транзакций пользователя."""
    wallet = db.query(WalletModel).filter(WalletModel.user_id == user_id).first()
    if not wallet:
        return []
    return (
        db.query(TransactionModel)
        .filter(TransactionModel.wallet_id == wallet.id)
        .order_by(TransactionModel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
