"""
Pydantic-схемы для платёжного модуля.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WalletOut(BaseModel):
    """Данные кошелька пользователя."""
    id: int
    user_id: int
    balance: float
    on_hold: float
    status: str
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class TopUpRequest(BaseModel):
    """Пополнение кошелька."""
    amount: float
    description: Optional[str] = ""


class HoldRequest(BaseModel):
    """Заморозка средств под закупку."""
    amount: float
    purchase_id: int
    description: Optional[str] = ""


class ReleaseRequest(BaseModel):
    """Разморозка средств."""
    amount: float
    purchase_id: int
    description: Optional[str] = ""


class EscrowDepositRequest(BaseModel):
    """Депозит в эскроу-счёт закупки."""
    purchase_id: int
    amount: float


class EscrowConfirmRequest(BaseModel):
    """Подтверждение эскроу (по закупке)."""
    purchase_id: int


class TransactionOut(BaseModel):
    """Данные транзакции."""
    id: int
    wallet_id: int
    type: str
    amount: float
    status: str
    reference_id: Optional[str]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
