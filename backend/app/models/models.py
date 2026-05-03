from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    balance = Column(Numeric(12, 2), default=Decimal("0.00"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CategoryModel(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    icon = Column(String(50), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurements = relationship("ProcurementModel", back_populates="category")


class ProcurementModel(Base):
    __tablename__ = "procurements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    city = Column(String(100), default="")
    delivery_address = Column(Text, default="")
    target_amount = Column(Numeric(12, 2), nullable=False)
    current_amount = Column(Numeric(12, 2), default=Decimal("0.00"))
    stop_at_amount = Column(Numeric(12, 2), nullable=True)
    unit = Column(String(20), default="units")
    price_per_unit = Column(Numeric(10, 2), nullable=True)
    commission_percent = Column(Numeric(4, 2), default=Decimal("0.00"))
    status = Column(String(20), default="draft", index=True)
    deadline = Column(DateTime, nullable=False)
    image_url = Column(String(500), default="")
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = relationship("CategoryModel", back_populates="procurements")
    organizer = relationship("UserModel", foreign_keys=[organizer_id])
    participants = relationship(
        "ParticipantModel", back_populates="procurement", cascade="all, delete-orphan"
    )
    messages = relationship(
        "ChatMessageModel", back_populates="procurement", cascade="all, delete-orphan"
    )


class ParticipantModel(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity = Column(Numeric(10, 2), default=Decimal("1.00"))
    amount = Column(Numeric(12, 2), default=Decimal("0.00"))
    status = Column(String(20), default="pending")
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurement = relationship("ProcurementModel", back_populates="participants")
    user = relationship("UserModel", foreign_keys=[user_id])


class PaymentModel(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=True)
    payment_type = Column(String(30), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), default="pending")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", foreign_keys=[user_id])
    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    room = Column(String(100), nullable=False, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    msg_type = Column(String(20), default="message")
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurement = relationship(
        "ProcurementModel", back_populates="messages", foreign_keys=[procurement_id]
    )
    user = relationship("UserModel", foreign_keys=[user_id])
