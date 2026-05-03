"""
Модели платёжного модуля: Wallet, Transaction, EscrowAccount, Commission.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

from app.database import Base


class WalletModel(Base):
    """Кошелёк пользователя. Статус: active | frozen | closed."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    balance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    on_hold = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Статус: active | frozen | closed
    status = Column(String(20), default="active", nullable=False)
    currency = Column(String(3), default="RUB", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TransactionModel(Base):
    """
    Транзакция кошелька.
    Типы: top_up | hold | commit | release | withdraw | refund | escrow_in | escrow_out | commission
    Статусы: pending | completed | failed | rolled_back
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False, index=True)
    # Тип операции
    type = Column(String(30), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    # Статус транзакции
    status = Column(String(20), default="pending", nullable=False)
    reference_id = Column(String(128), nullable=True)
    description = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class EscrowAccountModel(Base):
    """
    Эскроу-счёт для закупки.
    Статусы: active | released | disputed | refunded
    """
    __tablename__ = "escrow_accounts"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, unique=True, index=True)
    total_deposited = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    confirmations_received = Column(Integer, default=0, nullable=False)
    confirmations_required = Column(Integer, default=1, nullable=False)
    # Статус эскроу
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CommissionModel(Base):
    """
    Комиссионный сбор с закупки.
    Статусы: held | committed | released
    """
    __tablename__ = "commissions"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    percent = Column(Numeric(5, 2), nullable=False)
    # Статус комиссии
    status = Column(String(20), default="held", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
