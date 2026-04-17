import json
import os
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime,
    Numeric, Text, ForeignKey, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# ── Config ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Database ─────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Redis client (initialized on startup) ────────────────────────────────────
redis_client: Optional[aioredis.Redis] = None


# ── Models ────────────────────────────────────────────────────────────────────

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
    # status: draft | active | stopped | payment | completed | cancelled
    status = Column(String(20), default="draft", index=True)
    deadline = Column(DateTime, nullable=False)
    image_url = Column(String(500), default="")
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    category = relationship("CategoryModel", back_populates="procurements")
    organizer = relationship("UserModel", foreign_keys=[organizer_id])
    participants = relationship("ParticipantModel", back_populates="procurement",
                                cascade="all, delete-orphan")
    messages = relationship("ChatMessageModel", back_populates="procurement",
                            cascade="all, delete-orphan")


class ParticipantModel(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity = Column(Numeric(10, 2), default=Decimal("1.00"))
    amount = Column(Numeric(12, 2), default=Decimal("0.00"))
    # status: pending | confirmed | paid | delivered | cancelled
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
    # payment_type: deposit | withdrawal | procurement_payment
    payment_type = Column(String(30), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    # status: pending | succeeded | cancelled | refunded
    status = Column(String(30), default="pending")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", foreign_keys=[user_id])
    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    # room maps to procurement_id or a named channel (general, sales, support)
    room = Column(String(100), nullable=False, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # type: message | system
    msg_type = Column(String(20), default="message")
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurement = relationship("ProcurementModel", back_populates="messages",
                               foreign_keys=[procurement_id])
    user = relationship("UserModel", foreign_keys=[user_id])


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth helpers ──────────────────────────────────────────────────────────────
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


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user_id: int = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def admin_user(user: UserModel = Depends(current_user)) -> UserModel:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


# ── Redis Pub/Sub helper ─────────────────────────────────────────────────────
async def publish_event(channel: str, event: dict):
    """Publish an event to Redis Pub/Sub for the socket-service to relay."""
    if redis_client:
        try:
            await redis_client.publish(channel, json.dumps(event))
        except Exception:
            pass


# ── Schemas ───────────────────────────────────────────────────────────────────

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
    payment_type: str  # deposit | withdrawal | procurement_payment
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


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    if redis_client:
        await redis_client.aclose()

app = FastAPI(
    title="GroupBuy Backend API",
    version="2.0.0",
    description=(
        "REST API for the GroupBuy platform — group purchasing management.\n\n"
        "**Authentication**: Bearer JWT token. Obtain via `POST /auth/login`.\n\n"
        "**Roles**: regular users can manage their own data; admin users can manage all resources.\n\n"
        "Interactive docs: `/docs` (Swagger UI) · `/redoc` (ReDoc)"
    ),
    contact={"name": "GroupBuy Team"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(
        (UserModel.username == data.username) | (UserModel.email == data.email)
    ).first():
        raise HTTPException(status_code=400, detail="Username or email already taken")
    user = UserModel(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@app.post("/auth/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    token = create_token({"sub": str(user.id)})
    return {"access_token": token}


@app.get("/auth/me", response_model=UserOut)
def me(user: UserModel = Depends(current_user)):
    return _user_out(user)


# ── User CRUD (admin) ─────────────────────────────────────────────────────────
@app.get("/users", response_model=list[UserOut])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _=Depends(admin_user)):
    return [_user_out(u) for u in db.query(UserModel).offset(skip).limit(limit).all()]


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user)


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


# ── Categories ────────────────────────────────────────────────────────────────
@app.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(CategoryModel).filter(CategoryModel.is_active.is_(True)).all()


@app.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = CategoryModel(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@app.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = db.query(CategoryModel).filter(CategoryModel.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    db.commit()


# ── Procurements ──────────────────────────────────────────────────────────────
@app.get("/procurements", response_model=list[ProcurementOut])
def list_procurements(
    status: Optional[str] = None,
    city: Optional[str] = None,
    category_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(ProcurementModel)
    if status:
        q = q.filter(ProcurementModel.status == status)
    if city:
        q = q.filter(ProcurementModel.city.ilike(f"%{city}%"))
    if category_id:
        q = q.filter(ProcurementModel.category_id == category_id)
    items = q.order_by(ProcurementModel.created_at.desc()).offset(skip).limit(limit).all()
    return [_procurement_out(p) for p in items]


@app.post("/procurements", response_model=ProcurementOut, status_code=201)
async def create_procurement(
    data: ProcurementCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = ProcurementModel(
        organizer_id=user.id,
        **data.model_dump(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    # Notify via Redis Pub/Sub instead of direct socket call
    await publish_event("room:admin", {
        "type": "procurement_created",
        "procurement_id": p.id,
        "title": p.title,
        "organizer": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return _procurement_out(p)


@app.get("/procurements/{proc_id}", response_model=ProcurementOut)
def get_procurement(proc_id: int, db: Session = Depends(get_db)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    return _procurement_out(p)


@app.patch("/procurements/{proc_id}", response_model=ProcurementOut)
async def update_procurement(
    proc_id: int,
    data: ProcurementUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)

    # Notify via Redis Pub/Sub
    await publish_event("room:admin", {
        "type": "procurement_updated",
        "procurement_id": p.id,
        "status": p.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return _procurement_out(p)


@app.delete("/procurements/{proc_id}", status_code=204)
def delete_procurement(
    proc_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    db.delete(p)
    db.commit()


# ── Participants ──────────────────────────────────────────────────────────────
@app.get("/procurements/{proc_id}/participants", response_model=list[ParticipantOut])
def list_participants(proc_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return [_participant_out(pt) for pt in
            db.query(ParticipantModel).filter(ParticipantModel.procurement_id == proc_id).all()]


@app.post("/procurements/{proc_id}/join", response_model=ParticipantOut, status_code=201)
async def join_procurement(
    proc_id: int,
    data: ParticipantCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.status != "active":
        raise HTTPException(status_code=400, detail="Procurement is not active")
    existing = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active.is_(True),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already joined")
    amount = float(data.quantity) * float(p.price_per_unit or 0)
    pt = ParticipantModel(
        procurement_id=proc_id,
        user_id=user.id,
        quantity=data.quantity,
        amount=amount,
    )
    db.add(pt)
    # Update current_amount
    p.current_amount = float(p.current_amount) + amount
    if p.stop_at_amount and float(p.current_amount) >= float(p.stop_at_amount):
        p.status = "stopped"
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pt)

    # Notify via Redis Pub/Sub
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "participant_joined",
        "procurement_id": proc_id,
        "user_id": user.id,
        "username": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await publish_event("room:admin", {
        "type": "participant_joined",
        "procurement_id": proc_id,
        "user_id": user.id,
        "username": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return _participant_out(pt)


@app.delete("/procurements/{proc_id}/leave", status_code=204)
async def leave_procurement(
    proc_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    pt = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active.is_(True),
    ).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Not a participant")
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if p:
        p.current_amount = max(0, float(p.current_amount) - float(pt.amount))
        p.updated_at = datetime.now(timezone.utc)
    pt.is_active = False
    pt.status = "cancelled"
    db.commit()

    # Notify via Redis Pub/Sub
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "participant_left",
        "procurement_id": proc_id,
        "user_id": user.id,
        "username": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Payments ──────────────────────────────────────────────────────────────────
@app.get("/payments", response_model=list[PaymentOut])
def list_payments(
    skip: int = 0,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    q = db.query(PaymentModel)
    if not user.is_admin:
        q = q.filter(PaymentModel.user_id == user.id)
    return [_payment_out(pay) for pay in
            q.order_by(PaymentModel.created_at.desc()).offset(skip).limit(limit).all()]


@app.post("/payments", response_model=PaymentOut, status_code=201)
async def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    if data.payment_type not in ("deposit", "withdrawal", "procurement_payment"):
        raise HTTPException(status_code=400, detail="Invalid payment_type")
    pay = PaymentModel(
        user_id=user.id,
        procurement_id=data.procurement_id,
        payment_type=data.payment_type,
        amount=data.amount,
        description=data.description,
        status="succeeded",
    )
    db.add(pay)
    # Update user balance
    if data.payment_type == "deposit":
        user.balance = float(user.balance) + data.amount
    elif data.payment_type in ("withdrawal", "procurement_payment"):
        if float(user.balance) < data.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance = float(user.balance) - data.amount
    db.commit()
    db.refresh(pay)

    # Notify via Redis Pub/Sub
    await publish_event(f"room:user_{user.id}", {
        "type": "payment_update",
        "payment_id": pay.id,
        "payment_type": pay.payment_type,
        "amount": float(pay.amount),
        "status": pay.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return _payment_out(pay)


@app.get("/payments/{pay_id}", response_model=PaymentOut)
def get_payment(
    pay_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    pay = db.query(PaymentModel).filter(PaymentModel.id == pay_id).first()
    if not pay:
        raise HTTPException(status_code=404, detail="Payment not found")
    if pay.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _payment_out(pay)


# ── Chat messages ─────────────────────────────────────────────────────────────
@app.get("/chat/{room}/messages", response_model=list[ChatMessageOut])
def get_room_messages(
    room: str,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(current_user),
):
    msgs = (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.room == room)
        .order_by(ChatMessageModel.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [_chat_msg_out(m) for m in reversed(msgs)]


# ── Health / inter-service check ──────────────────────────────────────────────
@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "database": "ok" if db_ok else "error"}


# ── Internal endpoints (called by socket service) ─────────────────────────────
class SocketEvent(BaseModel):
    type: str
    room: str
    user_id: str
    text: str
    timestamp: str


@app.post("/internal/socket-event", status_code=204)
def receive_socket_event(event: SocketEvent, db: Session = Depends(get_db)):
    try:
        user_id_int = int(event.user_id) if event.user_id.isdigit() else None
    except (ValueError, AttributeError):
        user_id_int = None

    msg = ChatMessageModel(
        room=event.room,
        user_id=user_id_int,
        msg_type=event.type,
        text=event.text,
        timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
    )
    db.add(msg)
    db.commit()
    return None


# ── Change password ───────────────────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/auth/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    user.hashed_password = hash_password(data.new_password)
    db.commit()


# ── Admin statistics ──────────────────────────────────────────────────────────
@app.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db), _=Depends(admin_user)):
    from sqlalchemy import func
    total_users = db.query(func.count(UserModel.id)).scalar() or 0
    total_procurements = db.query(func.count(ProcurementModel.id)).scalar() or 0
    active_procurements = db.query(func.count(ProcurementModel.id)).filter(
        ProcurementModel.status == "active"
    ).scalar() or 0
    total_payments = db.query(func.count(PaymentModel.id)).scalar() or 0
    total_deposited = db.query(func.sum(PaymentModel.amount)).filter(
        PaymentModel.payment_type == "deposit",
        PaymentModel.status == "succeeded",
    ).scalar() or 0
    return {
        "total_users": total_users,
        "total_procurements": total_procurements,
        "active_procurements": active_procurements,
        "total_payments": total_payments,
        "total_deposited": float(total_deposited),
    }


# ── Output helpers (avoids Pydantic issues with Decimal/lazy-load) ────────────
def _user_out(u: UserModel) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_active": u.is_active,
        "is_admin": u.is_admin,
        "balance": float(u.balance or 0),
        "created_at": u.created_at,
    }


def _procurement_out(p: ProcurementModel) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description or "",
        "category_id": p.category_id,
        "organizer_id": p.organizer_id,
        "organizer_username": p.organizer.username if p.organizer else "",
        "city": p.city or "",
        "delivery_address": p.delivery_address or "",
        "target_amount": float(p.target_amount),
        "current_amount": float(p.current_amount or 0),
        "stop_at_amount": float(p.stop_at_amount) if p.stop_at_amount else None,
        "unit": p.unit or "units",
        "price_per_unit": float(p.price_per_unit) if p.price_per_unit else None,
        "commission_percent": float(p.commission_percent or 0),
        "status": p.status,
        "deadline": p.deadline,
        "image_url": p.image_url or "",
        "is_featured": p.is_featured,
        "participant_count": len([pt for pt in p.participants if pt.is_active]),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _participant_out(pt: ParticipantModel) -> dict:
    return {
        "id": pt.id,
        "procurement_id": pt.procurement_id,
        "user_id": pt.user_id,
        "username": pt.user.username if pt.user else "",
        "quantity": float(pt.quantity or 1),
        "amount": float(pt.amount or 0),
        "status": pt.status,
        "is_active": pt.is_active,
        "joined_at": pt.joined_at,
    }


def _payment_out(pay: PaymentModel) -> dict:
    return {
        "id": pay.id,
        "user_id": pay.user_id,
        "procurement_id": pay.procurement_id,
        "payment_type": pay.payment_type,
        "amount": float(pay.amount),
        "status": pay.status,
        "description": pay.description or "",
        "created_at": pay.created_at,
    }


def _chat_msg_out(m: ChatMessageModel) -> dict:
    return {
        "id": m.id,
        "room": m.room,
        "user_id": m.user_id,
        "username": m.user.username if m.user else None,
        "msg_type": m.msg_type,
        "text": m.text,
        "timestamp": m.timestamp,
    }
