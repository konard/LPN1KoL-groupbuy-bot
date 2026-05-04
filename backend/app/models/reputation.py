"""
Модели репутационного модуля: Review, Complaint, ReputationScore.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from app.database import Base


class ReviewModel(Base):
    """Отзыв пользователя о другом участнике закупки."""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    # Рейтинг от 1 до 5
    rating = Column(Integer, nullable=False)
    comment = Column(Text, default="", nullable=True)
    is_anonymous = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ComplaintModel(Base):
    """
    Жалоба на пользователя.
    Статусы: open | investigating | resolved | dismissed
    """
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    reason = Column(Text, nullable=False)
    evidence_url = Column(String(512), nullable=True)
    # Статус жалобы
    status = Column(String(20), default="open", nullable=False)
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ReputationScoreModel(Base):
    """Агрегированная репутация пользователя. Один ряд на пользователя."""
    __tablename__ = "reputation_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    score = Column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    total_reviews = Column(Integer, default=0, nullable=False)
    total_complaints = Column(Integer, default=0, nullable=False)
    # Флаг автоблокировки (5+ нерешённых жалоб)
    is_blocked = Column(Boolean, default=False, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
