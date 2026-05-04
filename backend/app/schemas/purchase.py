"""
Pydantic-схемы для модуля закупок.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PurchaseCreate(BaseModel):
    """Создание новой закупки."""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    min_quantity: int = 1
    commission_pct: float = 0.0


class PurchaseOut(BaseModel):
    """Данные закупки в ответе API."""
    id: int
    organizer_id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    status: str
    min_quantity: int
    commission_pct: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddCandidateRequest(BaseModel):
    """Добавление поставщика-кандидата в сессию голосования."""
    supplier_id: int
    price: float
    description: Optional[str] = None


class CastVoteRequest(BaseModel):
    """Голосование за кандидата."""
    candidate_id: int


class CandidateOut(BaseModel):
    """Данные кандидата."""
    id: int
    session_id: int
    supplier_id: int
    price: float
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class VotingSessionOut(BaseModel):
    """Данные сессии голосования."""
    id: int
    purchase_id: int
    status: str
    winner_id: Optional[int]
    created_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True
