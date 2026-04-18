"""
GroupBuy Unified Service — Python + FastAPI
Merges all service roles into a single container:
  - REST API (auth, users, procurements, payments, chat)
  - WebSocket broker (Redis Pub/Sub)
  - Admin panel (Jinja2 SSR)
  - Analytics (in-memory stats, XLSX/CSV reports)

Routing:
  /api/*        — REST API (Swagger at /api/docs)
  /ws/{room}    — WebSocket broker
  /admin/*      — Admin panel (SSR)
  /analytics/*  — Analytics stats & reports
  /health       — Top-level health check
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import jwt
import openpyxl
import redis.asyncio as aioredis
from fastapi import (
    Cookie, Depends, FastAPI, Form, HTTPException, Query,
    Request, Response, WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.routing import APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric,
    String, Text, create_engine, text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("groupbuy")

# ── Configuration ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost,http://localhost:5173,http://localhost:8080"
).split(",")
REDIS_URL = os.getenv("REDIS_URL", "")

# ── Database ───────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ────────────────────────────────────────────────────────────────

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


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth helpers ───────────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, hashed: str) -> bool:
    salt, h = hashed.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def create_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token_data(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token_data(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(UserModel).filter(UserModel.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def admin_user(user: UserModel = Depends(current_user)) -> UserModel:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


# ── Output helpers ─────────────────────────────────────────────────────────────

def _user_out(u: UserModel) -> dict:
    return {
        "id": u.id, "username": u.username, "email": u.email,
        "is_active": u.is_active, "is_admin": u.is_admin,
        "balance": float(u.balance or 0), "created_at": u.created_at,
    }


def _procurement_out(p: ProcurementModel) -> dict:
    return {
        "id": p.id, "title": p.title, "description": p.description or "",
        "category_id": p.category_id, "organizer_id": p.organizer_id,
        "organizer_username": p.organizer.username if p.organizer else "",
        "city": p.city or "", "delivery_address": p.delivery_address or "",
        "target_amount": float(p.target_amount),
        "current_amount": float(p.current_amount or 0),
        "stop_at_amount": float(p.stop_at_amount) if p.stop_at_amount else None,
        "unit": p.unit or "units",
        "price_per_unit": float(p.price_per_unit) if p.price_per_unit else None,
        "commission_percent": float(p.commission_percent or 0),
        "status": p.status, "deadline": p.deadline,
        "image_url": p.image_url or "", "is_featured": p.is_featured,
        "participant_count": len([pt for pt in p.participants if pt.is_active]),
        "created_at": p.created_at, "updated_at": p.updated_at,
    }


def _participant_out(pt: ParticipantModel) -> dict:
    return {
        "id": pt.id, "procurement_id": pt.procurement_id, "user_id": pt.user_id,
        "username": pt.user.username if pt.user else "",
        "quantity": float(pt.quantity or 1), "amount": float(pt.amount or 0),
        "status": pt.status, "is_active": pt.is_active, "joined_at": pt.joined_at,
    }


def _payment_out(pay: PaymentModel) -> dict:
    return {
        "id": pay.id, "user_id": pay.user_id, "procurement_id": pay.procurement_id,
        "payment_type": pay.payment_type, "amount": float(pay.amount),
        "status": pay.status, "description": pay.description or "",
        "created_at": pay.created_at,
    }


def _chat_msg_out(m: ChatMessageModel) -> dict:
    return {
        "id": m.id, "room": m.room, "user_id": m.user_id,
        "username": m.user.username if m.user else None,
        "msg_type": m.msg_type, "text": m.text, "timestamp": m.timestamp,
    }


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    icon: str = ""


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str
    parent_id: Optional[int]
    icon: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProcurementCreate(BaseModel):
    title: str
    description: str = ""
    category_id: Optional[int] = None
    city: str = ""
    delivery_address: str = ""
    target_amount: float
    stop_at_amount: Optional[float] = None
    unit: str = "units"
    price_per_unit: Optional[float] = None
    commission_percent: float = 0.0
    deadline: datetime
    image_url: str = ""
    is_featured: bool = False


class ProcurementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    city: Optional[str] = None
    delivery_address: Optional[str] = None
    target_amount: Optional[float] = None
    stop_at_amount: Optional[float] = None
    unit: Optional[str] = None
    price_per_unit: Optional[float] = None
    commission_percent: Optional[float] = None
    deadline: Optional[datetime] = None
    image_url: Optional[str] = None
    is_featured: Optional[bool] = None


class ProcurementOut(BaseModel):
    id: int
    title: str
    description: str
    category_id: Optional[int]
    organizer_id: int
    organizer_username: str
    city: str
    delivery_address: str
    target_amount: float
    current_amount: float
    stop_at_amount: Optional[float]
    unit: str
    price_per_unit: Optional[float]
    commission_percent: float
    status: str
    deadline: datetime
    image_url: str
    is_featured: bool
    participant_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParticipantCreate(BaseModel):
    quantity: float = 1.0


class ParticipantOut(BaseModel):
    id: int
    procurement_id: int
    user_id: int
    username: str
    quantity: float
    amount: float
    status: str
    is_active: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    payment_type: str
    amount: float
    procurement_id: Optional[int] = None
    description: str = ""


class PaymentOut(BaseModel):
    id: int
    user_id: int
    procurement_id: Optional[int]
    payment_type: str
    amount: float
    status: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageOut(BaseModel):
    id: int
    room: str
    user_id: Optional[int]
    username: Optional[str]
    msg_type: str
    text: str
    timestamp: datetime

    class Config:
        from_attributes = True


class SocketEvent(BaseModel):
    type: str
    room: str
    user_id: str
    text: str
    timestamp: str


# ── REST API router ────────────────────────────────────────────────────────────
api = APIRouter(prefix="/api", tags=["api"])


@api.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(
        (UserModel.username == data.username) | (UserModel.email == data.email)
    ).first():
        raise HTTPException(400, "Username or email already taken")
    user = UserModel(
        username=data.username, email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@api.post("/auth/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    return {"access_token": create_token({"sub": str(user.id)})}


@api.get("/auth/me", response_model=UserOut)
def me(user: UserModel = Depends(current_user)):
    return _user_out(user)


@api.get("/users", response_model=list[UserOut])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _=Depends(admin_user)):
    return [_user_out(u) for u in db.query(UserModel).offset(skip).limit(limit).all()]


@api.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return _user_out(user)


@api.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@api.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    db.delete(user)
    db.commit()


@api.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(CategoryModel).filter(CategoryModel.is_active).all()


@api.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = CategoryModel(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@api.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = db.query(CategoryModel).filter(CategoryModel.id == cat_id).first()
    if not cat:
        raise HTTPException(404, "Category not found")
    cat.is_active = False
    db.commit()


@api.get("/procurements", response_model=list[ProcurementOut])
def list_procurements(
    status: Optional[str] = None, city: Optional[str] = None,
    category_id: Optional[int] = None, skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(ProcurementModel)
    if status:
        q = q.filter(ProcurementModel.status == status)
    if city:
        q = q.filter(ProcurementModel.city.ilike(f"%{city}%"))
    if category_id:
        q = q.filter(ProcurementModel.category_id == category_id)
    return [_procurement_out(p) for p in
            q.order_by(ProcurementModel.created_at.desc()).offset(skip).limit(limit).all()]


@api.post("/procurements", response_model=ProcurementOut, status_code=201)
def create_procurement(
    data: ProcurementCreate, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = ProcurementModel(organizer_id=user.id, **data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _procurement_out(p)


@api.get("/procurements/{proc_id}", response_model=ProcurementOut)
def get_procurement(proc_id: int, db: Session = Depends(get_db)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(404, "Procurement not found")
    return _procurement_out(p)


@api.patch("/procurements/{proc_id}", response_model=ProcurementOut)
def update_procurement(
    proc_id: int, data: ProcurementUpdate, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(404, "Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not the organizer")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return _procurement_out(p)


@api.delete("/procurements/{proc_id}", status_code=204)
def delete_procurement(
    proc_id: int, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(404, "Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not the organizer")
    db.delete(p)
    db.commit()


@api.get("/procurements/{proc_id}/participants", response_model=list[ParticipantOut])
def list_participants(proc_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return [_participant_out(pt) for pt in
            db.query(ParticipantModel).filter(ParticipantModel.procurement_id == proc_id).all()]


@api.post("/procurements/{proc_id}/join", response_model=ParticipantOut, status_code=201)
def join_procurement(
    proc_id: int, data: ParticipantCreate, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(404, "Procurement not found")
    if p.status != "active":
        raise HTTPException(400, "Procurement is not active")
    if db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active,
    ).first():
        raise HTTPException(400, "Already joined")
    amount = float(data.quantity) * float(p.price_per_unit or 0)
    pt = ParticipantModel(procurement_id=proc_id, user_id=user.id, quantity=data.quantity, amount=amount)
    db.add(pt)
    p.current_amount = float(p.current_amount) + amount
    if p.stop_at_amount and float(p.current_amount) >= float(p.stop_at_amount):
        p.status = "stopped"
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pt)
    return _participant_out(pt)


@api.delete("/procurements/{proc_id}/leave", status_code=204)
def leave_procurement(proc_id: int, db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    pt = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active,
    ).first()
    if not pt:
        raise HTTPException(404, "Not a participant")
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if p:
        p.current_amount = max(0, float(p.current_amount) - float(pt.amount))
        p.updated_at = datetime.now(timezone.utc)
    pt.is_active = False
    pt.status = "cancelled"
    db.commit()


@api.get("/payments", response_model=list[PaymentOut])
def list_payments(
    skip: int = 0, limit: int = 50, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    q = db.query(PaymentModel)
    if not user.is_admin:
        q = q.filter(PaymentModel.user_id == user.id)
    return [_payment_out(pay) for pay in
            q.order_by(PaymentModel.created_at.desc()).offset(skip).limit(limit).all()]


@api.post("/payments", response_model=PaymentOut, status_code=201)
def create_payment(
    data: PaymentCreate, db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    if data.payment_type not in ("deposit", "withdrawal", "procurement_payment"):
        raise HTTPException(400, "Invalid payment_type")
    pay = PaymentModel(
        user_id=user.id, procurement_id=data.procurement_id,
        payment_type=data.payment_type, amount=data.amount,
        description=data.description, status="succeeded",
    )
    db.add(pay)
    if data.payment_type == "deposit":
        user.balance = float(user.balance) + data.amount
    elif data.payment_type in ("withdrawal", "procurement_payment"):
        if float(user.balance) < data.amount:
            raise HTTPException(400, "Insufficient balance")
        user.balance = float(user.balance) - data.amount
    db.commit()
    db.refresh(pay)
    return _payment_out(pay)


@api.get("/payments/{pay_id}", response_model=PaymentOut)
def get_payment(pay_id: int, db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    pay = db.query(PaymentModel).filter(PaymentModel.id == pay_id).first()
    if not pay:
        raise HTTPException(404, "Payment not found")
    if pay.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "Forbidden")
    return _payment_out(pay)


@api.get("/chat/{room}/messages", response_model=list[ChatMessageOut])
def get_room_messages(
    room: str, limit: int = Query(50, le=200),
    db: Session = Depends(get_db), _=Depends(current_user),
):
    msgs = (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.room == room)
        .order_by(ChatMessageModel.timestamp.desc())
        .limit(limit).all()
    )
    return [_chat_msg_out(m) for m in reversed(msgs)]


@api.get("/health")
def api_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "database": "ok" if db_ok else "error"}


@api.post("/internal/socket-event", status_code=204)
def receive_socket_event(event: SocketEvent, db: Session = Depends(get_db)):
    try:
        user_id_int = int(event.user_id) if event.user_id.isdigit() else None
    except (ValueError, AttributeError):
        user_id_int = None
    msg = ChatMessageModel(
        room=event.room, user_id=user_id_int, msg_type=event.type, text=event.text,
        timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
    )
    db.add(msg)
    db.commit()


# ── WebSocket broker ───────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[tuple[WebSocket, str]]] = {}

    async def connect(self, room_id: str, ws: WebSocket, user_id: str):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append((ws, user_id))

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.rooms:
            self.rooms[room_id] = [(w, uid) for w, uid in self.rooms[room_id] if w is not ws]

    async def deliver(self, room_id: str, message: dict, exclude: Optional[WebSocket] = None):
        dead = []
        for ws, _ in list(self.rooms.get(room_id, [])):
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    def room_users(self, room_id: str) -> list[str]:
        return [uid for _, uid in self.rooms.get(room_id, [])]


_manager = ConnectionManager()
_ws_history: dict[str, list[dict]] = {}
_redis_pool: Optional[aioredis.Redis] = None


def _get_redis() -> Optional[aioredis.Redis]:
    global _redis_pool
    if not REDIS_URL:
        return None
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


def _add_to_history(room_id: str, msg: dict):
    _ws_history.setdefault(room_id, [])
    _ws_history[room_id].append(msg)
    _ws_history[room_id] = _ws_history[room_id][-50:]


async def _publish(room_id: str, message: dict):
    redis = _get_redis()
    if redis:
        await redis.publish(f"room:{room_id}", json.dumps(message))
        await redis.publish("room:admin", json.dumps(message))
    else:
        await _manager.deliver(room_id, message)


async def _redis_subscriber():
    redis = _get_redis()
    if not redis:
        return
    pubsub = redis.pubsub()
    await pubsub.psubscribe("room:*")
    async for raw in pubsub.listen():
        if raw["type"] != "pmessage":
            continue
        channel: str = raw["channel"]
        try:
            message = json.loads(raw["data"])
        except (json.JSONDecodeError, TypeError):
            continue
        parts = channel.split(":", 1)
        if len(parts) == 2:
            await _manager.deliver(parts[1], message)


ws_router = APIRouter(tags=["websocket"])


@ws_router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str = Query(...)):
    payload = decode_token_data(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user_id = str(payload.get("sub", "unknown"))
    await _manager.connect(room_id, websocket, user_id)

    for msg in _ws_history.get(room_id, []):
        await websocket.send_json(msg)

    join_msg = {
        "type": "system", "room": room_id, "user_id": user_id,
        "text": f"User {user_id} joined",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _add_to_history(room_id, join_msg)
    await _publish(room_id, join_msg)

    try:
        while True:
            data = await websocket.receive_json()
            msg = {
                "type": "message", "room": room_id, "user_id": user_id,
                "text": str(data.get("text", ""))[:2000],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _add_to_history(room_id, msg)
            await _publish(room_id, msg)
    except WebSocketDisconnect:
        _manager.disconnect(room_id, websocket)
        leave_msg = {
            "type": "system", "room": room_id, "user_id": user_id,
            "text": f"User {user_id} left",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _add_to_history(room_id, leave_msg)
        await _publish(room_id, leave_msg)


@ws_router.get("/rooms/{room_id}/history")
def get_ws_history(room_id: str):
    return _ws_history.get(room_id, [])


@ws_router.get("/rooms/{room_id}/users")
def get_ws_users(room_id: str):
    return _manager.room_users(room_id)


# ── Admin panel router ─────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_api_base():
    return "http://localhost:8000/api"


async def _admin_get(path: str, token: str) -> dict | list | None:
    import httpx
    async with httpx.AsyncClient(base_url=_admin_api_base(), timeout=10) as client:
        r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        return r.json() if r.status_code == 200 else None


async def _admin_patch(path: str, token: str, data: dict) -> bool:
    import httpx
    async with httpx.AsyncClient(base_url=_admin_api_base(), timeout=10) as client:
        r = await client.patch(path, json=data, headers={"Authorization": f"Bearer {token}"})
        return r.status_code == 200


async def _admin_delete(path: str, token: str) -> bool:
    import httpx
    async with httpx.AsyncClient(base_url=_admin_api_base(), timeout=10) as client:
        r = await client.delete(path, headers={"Authorization": f"Bearer {token}"})
        return r.status_code in (200, 204)


@admin_router.get("/", response_class=HTMLResponse)
async def admin_index(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/admin/login")
    users = await _admin_get("/users", admin_token) or []
    health = await _admin_get("/health", admin_token) or {}
    return templates.TemplateResponse("index.html", {"request": request, "users": users, "health": health})


@admin_router.get("/procurements", response_class=HTMLResponse)
async def admin_procurements(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/admin/login")
    procurements = await _admin_get("/procurements?limit=100", admin_token) or []
    categories = await _admin_get("/categories", admin_token) or []
    return templates.TemplateResponse("procurements.html", {
        "request": request, "procurements": procurements, "categories": categories,
    })


@admin_router.post("/procurements/{proc_id}/status")
async def admin_set_status(
    proc_id: int, new_status: str = Form(...),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/admin/login")
    await _admin_patch(f"/procurements/{proc_id}", admin_token, {"status": new_status})
    return RedirectResponse("/admin/procurements", status_code=302)


@admin_router.post("/procurements/{proc_id}/delete")
async def admin_delete_procurement(proc_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/admin/login")
    await _admin_delete(f"/procurements/{proc_id}", admin_token)
    return RedirectResponse("/admin/procurements", status_code=302)


@admin_router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@admin_router.post("/login")
async def admin_login(
    response: Response, username: str = Form(...), password: str = Form(...),
):
    import httpx
    async with httpx.AsyncClient(base_url=_admin_api_base(), timeout=10) as client:
        r = await client.post("/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        return RedirectResponse("/admin/login?error=1", status_code=302)
    token = r.json()["access_token"]
    resp = RedirectResponse("/admin/", status_code=302)
    resp.set_cookie("admin_token", token, httponly=True, samesite="lax")
    return resp


@admin_router.get("/logout")
async def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("admin_token")
    return resp


@admin_router.post("/users/{user_id}/toggle-active")
async def admin_toggle_active(user_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/admin/login")
    user = await _admin_get(f"/users/{user_id}", admin_token)
    if user:
        await _admin_patch(f"/users/{user_id}", admin_token, {"is_active": not user["is_active"]})
    return RedirectResponse("/admin/", status_code=302)


@admin_router.post("/users/{user_id}/delete")
async def admin_delete_user(user_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/admin/login")
    await _admin_delete(f"/users/{user_id}", admin_token)
    return RedirectResponse("/admin/", status_code=302)


# ── Analytics router ───────────────────────────────────────────────────────────
analytics_event_store: list[dict[str, Any]] = []
analytics_purchase_stats: dict[str, dict] = {}
analytics_payment_stats: dict[str, dict] = {}
analytics_reputation_stats: dict[str, dict] = {}
analytics_search_stats: dict[str, Any] = {"total_queries": 0, "queries": []}

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


def _generate_purchases_xlsx() -> bytes:
    rows = [e for e in analytics_event_store if "purchase" in e.get("topic", "")]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Purchase Events"
    ws.append(["Timestamp", "Topic", "Purchase ID", "User ID"])
    for row in rows:
        p = row.get("payload", {})
        ws.append([row.get("received_at", ""), row.get("topic", ""),
                   p.get("purchaseId", ""), p.get("userId", "")])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _generate_payments_csv() -> bytes:
    rows = [e for e in analytics_event_store if "payment" in e.get("topic", "")]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp", "Topic", "User ID", "Amount"])
    for row in rows:
        p = row.get("payload", {})
        writer.writerow([row.get("received_at", ""), row.get("topic", ""),
                         p.get("userId", ""), p.get("amount", "")])
    return buf.getvalue().encode("utf-8-sig")


@analytics_router.get("/health")
def analytics_health():
    return {"status": "ok", "service": "analytics", "events": len(analytics_event_store)}


@analytics_router.get("/stats/purchases")
def analytics_purchases():
    return {"success": True, "data": analytics_purchase_stats}


@analytics_router.get("/stats/payments")
def analytics_payments():
    return {"success": True, "data": analytics_payment_stats}


@analytics_router.get("/stats/reputation")
def analytics_reputation():
    return {"success": True, "data": analytics_reputation_stats}


@analytics_router.get("/stats/search")
def analytics_search():
    return {"success": True, "data": analytics_search_stats}


@analytics_router.get("/stats/summary")
def analytics_summary():
    return {
        "success": True,
        "data": {
            "total_events": len(analytics_event_store),
            "purchases_tracked": len(analytics_purchase_stats),
            "users_tracked": len(analytics_payment_stats),
            "reputation_profiles": len(analytics_reputation_stats),
            "search_queries": analytics_search_stats["total_queries"],
        },
    }


@analytics_router.post("/events")
async def ingest_event(request: Request):
    """Ingest an analytics event (replaces Kafka consumer for unified mode)."""
    body = await request.json()
    topic = body.get("topic", "unknown")
    payload = body.get("payload", {})
    received_at = datetime.now(timezone.utc).isoformat()
    analytics_event_store.append({"topic": topic, "payload": payload, "received_at": received_at})
    if "purchaseId" in payload:
        pid = payload["purchaseId"]
        analytics_purchase_stats.setdefault(pid, {"events": 0, "votes": 0})
        analytics_purchase_stats[pid]["events"] += 1
    return {"success": True}


@analytics_router.get("/reports/purchases/download")
def download_purchases_xlsx():
    data = _generate_purchases_xlsx()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=purchases.xlsx"},
    )


@analytics_router.get("/reports/payments/download")
def download_payments_csv():
    data = _generate_payments_csv()
    return Response(
        content=data, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments.csv"},
    )


# ── Application assembly ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if REDIS_URL:
        asyncio.create_task(_redis_subscriber())
        logger.info("Redis Pub/Sub subscriber started")
    else:
        logger.info("No REDIS_URL set — running without Redis (single-process mode)")
    yield
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()


app = FastAPI(
    title="GroupBuy Unified Service",
    description=(
        "Single-container GroupBuy platform. "
        "REST API at /api/docs · WebSocket at /ws/{room} · "
        "Admin at /admin/ · Analytics at /analytics/"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api)
app.include_router(ws_router)
app.include_router(admin_router)
app.include_router(analytics_router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok",
        "database": "ok" if db_ok else "error",
        "websocket_rooms": len(_manager.rooms),
        "analytics_events": len(analytics_event_store),
    }
