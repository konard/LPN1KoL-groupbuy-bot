"""
Модели для закупок: Purchase, VotingSession, Candidate, Vote.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)

from app.database import Base


class PurchaseModel(Base):
    """Закупка (groupbuy). Жизненный цикл: draft → open → voting → closed/cancelled."""
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="", nullable=True)
    category = Column(String(128), default="", nullable=True)
    # Статус: draft | open | voting | closed | cancelled
    status = Column(String(20), default="draft", nullable=False, index=True)
    min_quantity = Column(Integer, default=1, nullable=False)
    commission_pct = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class VotingSessionModel(Base):
    """Сессия голосования за поставщика."""
    __tablename__ = "voting_sessions"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    # Статус: active | closed | tie
    status = Column(String(20), default="active", nullable=False)
    winner_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime, nullable=True)


class CandidateModel(Base):
    """Кандидат-поставщик в сессии голосования."""
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("voting_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    description = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class VoteModel(Base):
    """Голос пользователя за кандидата. Один голос на сессию."""
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("voting_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_vote_session_user"),
    )
