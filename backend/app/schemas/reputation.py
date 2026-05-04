"""
Pydantic-схемы для репутационного модуля.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateReviewRequest(BaseModel):
    """Создание отзыва о пользователе."""
    target_id: int
    purchase_id: Optional[int] = None
    # Рейтинг от 1 до 5
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = ""
    is_anonymous: bool = False


class ReviewOut(BaseModel):
    """Данные отзыва."""
    id: int
    # author_id скрыт, если is_anonymous=True
    author_id: Optional[int]
    target_id: int
    purchase_id: Optional[int]
    rating: int
    comment: Optional[str]
    is_anonymous: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FileComplaintRequest(BaseModel):
    """Подача жалобы на пользователя."""
    target_id: int
    purchase_id: Optional[int] = None
    reason: str
    evidence_url: Optional[str] = None


class ResolveComplaintRequest(BaseModel):
    """Разрешение жалобы (только для администраторов)."""
    # Статус: resolved | dismissed
    status: str
    resolution: Optional[str] = None


class ComplaintOut(BaseModel):
    """Данные жалобы."""
    id: int
    reporter_id: int
    target_id: int
    purchase_id: Optional[int]
    reason: str
    evidence_url: Optional[str]
    status: str
    resolution: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReputationScoreOut(BaseModel):
    """Репутационный балл пользователя."""
    user_id: int
    score: float
    total_reviews: int
    total_complaints: int
    is_blocked: bool
    updated_at: datetime

    class Config:
        from_attributes = True
