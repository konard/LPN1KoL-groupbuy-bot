import json
import os
import jwt
import hashlib
import secrets
import smtplib
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from contextlib import asynccontextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
# Public path prefix under which the API is exposed via the reverse proxy.
# Empty by default (direct access); set to "/api" when served behind nginx so
# Swagger UI at /api/docs correctly references /api/openapi.json.
ROOT_PATH = os.getenv("ROOT_PATH", "")

# ── Email/SMTP Config ────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
LOGIN_CODE_EXPIRE_MINUTES = int(os.getenv("LOGIN_CODE_EXPIRE_MINUTES", "10"))

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
    phone = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    balance = Column(Numeric(12, 2), default=Decimal("0.00"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class LoginCodeModel(Base):
    """One-time login codes sent to user email after phone-based login attempt."""
    __tablename__ = "login_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", foreign_keys=[user_id])


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
    read_by = Column(Text, default="")  # CSV list of user ids that have read the message

    procurement = relationship("ProcurementModel", back_populates="messages",
                               foreign_keys=[procurement_id])
    user = relationship("UserModel", foreign_keys=[user_id])


class NotificationModel(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # kind: system | procurement | payment | vote | invitation | complaint
    kind = Column(String(30), default="system")
    title = Column(String(200), default="")
    body = Column(Text, default="")
    link = Column(String(500), default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", foreign_keys=[user_id])


class VoteModel(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # option: free-form string (e.g. supplier id, "yes"/"no", candidate name)
    option = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])
    user = relationship("UserModel", foreign_keys=[user_id])


class ComplaintModel(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=True)
    subject = Column(String(200), default="")
    body = Column(Text, default="")
    # status: open | in_review | resolved | rejected
    status = Column(String(30), default="open", index=True)
    resolution = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    reporter = relationship("UserModel", foreign_keys=[reporter_id])
    target_user = relationship("UserModel", foreign_keys=[target_user_id])
    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])


class ReviewModel(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=True)
    rating = Column(Integer, nullable=False)  # 1..5
    body = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = relationship("UserModel", foreign_keys=[author_id])
    target_user = relationship("UserModel", foreign_keys=[target_user_id])
    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])


class InvitationModel(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True, index=True)
    procurement_id = Column(Integer, ForeignKey("procurements.id"), nullable=False, index=True)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invitee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # status: pending | accepted | declined
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    procurement = relationship("ProcurementModel", foreign_keys=[procurement_id])
    inviter = relationship("UserModel", foreign_keys=[inviter_id])
    invitee = relationship("UserModel", foreign_keys=[invitee_id])


class ActivityLogModel(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    target = Column(String(200), default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", foreign_keys=[user_id])


Base.metadata.create_all(bind=engine)

# ── Lightweight migration for pre-existing SQLite DBs ─────────────────────────
def _ensure_column(table: str, column: str, col_ddl: str):
    with engine.begin() as conn:
        try:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            cols = {r[1] for r in rows}
            if column not in cols:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col_ddl}")
        except Exception:
            pass


if DATABASE_URL.startswith("sqlite"):
    _ensure_column("chat_messages", "read_by", "read_by TEXT DEFAULT ''")
    _ensure_column("users", "phone", "phone TEXT NOT NULL DEFAULT ''")


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


# ── Email helper ──────────────────────────────────────────────────────────────
def send_login_code_email(to_email: str, code: str) -> bool:
    """Send a one-time login code to the user's registered email address."""
    if not SMTP_USER or not SMTP_PASSWORD:
        # In development without SMTP configured, print the code to stdout
        print(f"[DEV] Login code for {to_email}: {code}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Ваш код входа в GroupBuy"
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        text_body = f"Ваш код для входа: {code}\nКод действителен {LOGIN_CODE_EXPIRE_MINUTES} минут."
        html_body = (
            f"<p>Ваш код для входа в <b>GroupBuy</b>:</p>"
            f"<h2 style='letter-spacing:4px'>{code}</h2>"
            f"<p>Код действителен {LOGIN_CODE_EXPIRE_MINUTES} минут.</p>"
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send login code email: {e}")
        return False


def _mask_email(email: str) -> str:
    """Return partially masked email for the API hint, e.g. u***@example.com."""
    parts = email.split("@", 1)
    if len(parts) != 2:
        return "***"
    local, domain = parts
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    phone: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    phone: str
    email: str
    is_active: bool
    is_admin: bool
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    phone: str
    password: str


class LoginCodeVerify(BaseModel):
    phone: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginCodeResponse(BaseModel):
    detail: str
    email_hint: str


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
    root_path=ROOT_PATH,
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
    """Register a new user. Requires username, phone number, email, and password."""
    conflict = db.query(UserModel).filter(
        (UserModel.username == data.username)
        | (UserModel.email == data.email)
        | (UserModel.phone == data.phone)
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Username, phone, or email already taken")
    user = UserModel(
        username=data.username,
        phone=data.phone,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@app.post("/auth/login", response_model=LoginCodeResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Step 1 of phone-based login.

    Validates phone + password. On success, generates a one-time 6-digit code
    and sends it to the email address the user provided at registration.
    The client must then call POST /auth/verify-code with the phone and code
    to receive the Bearer token.
    """
    user = db.query(UserModel).filter(UserModel.phone == data.phone).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Invalidate any previous unused codes for this user
    db.query(LoginCodeModel).filter(
        LoginCodeModel.user_id == user.id,
        LoginCodeModel.used.is_(False),
    ).update({"used": True})

    code = f"{random.randint(0, 999999):06d}"
    login_code = LoginCodeModel(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=LOGIN_CODE_EXPIRE_MINUTES),
    )
    db.add(login_code)
    db.commit()

    send_login_code_email(user.email, code)

    return {
        "detail": "Verification code sent to your registered email",
        "email_hint": _mask_email(user.email),
    }


@app.post("/auth/verify-code", response_model=TokenResponse)
def verify_code(data: LoginCodeVerify, db: Session = Depends(get_db)):
    """
    Step 2 of phone-based login.

    Validates the one-time code sent to the user's email after POST /auth/login.
    Returns a Bearer JWT token on success.
    """
    user = db.query(UserModel).filter(UserModel.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone or code")

    now = datetime.now(timezone.utc)
    login_code = db.query(LoginCodeModel).filter(
        LoginCodeModel.user_id == user.id,
        LoginCodeModel.code == data.code,
        LoginCodeModel.used.is_(False),
        LoginCodeModel.expires_at > now,
    ).first()

    if not login_code:
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")

    login_code.used = True
    db.commit()

    token = create_token({"sub": str(user.id)})
    return {"access_token": token}


@app.get("/auth/me", response_model=UserOut)
def me(user: UserModel = Depends(current_user)):
    return _user_out(user)


# ── User CRUD (admin) ─────────────────────────────────────────────────────────
@app.get("/users", response_model=list[UserOut])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _=Depends(admin_user)):
    return [_user_out(u) for u in db.query(UserModel).offset(skip).limit(limit).all()]


# NOTE: literal-prefix routes (/users/search, /users/by-email/...) are declared
# before /users/{user_id} so FastAPI matches them correctly.
@app.get("/users/search", response_model=list[UserOut])
def search_users_route(
    q: str = Query("", min_length=0),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: UserModel = Depends(current_user),
):
    """Search users by username or email substring (any authenticated user)."""
    query = db.query(UserModel)
    if q:
        like = f"%{q}%"
        query = query.filter((UserModel.username.ilike(like)) | (UserModel.email.ilike(like)))
    return [_user_out(u) for u in query.order_by(UserModel.id).limit(limit).all()]


@app.get("/users/by-email/{email}", response_model=UserOut)
def user_by_email_route(email: str, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user)


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


# ── User balance ─────────────────────────────────────────────────────────────
@app.get("/users/{user_id}/balance")
def get_balance(user_id: int, db: Session = Depends(get_db), requester: UserModel = Depends(current_user)):
    if requester.id != user_id and not requester.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user.id, "balance": float(user.balance or 0)}


class BalanceUpdate(BaseModel):
    amount: float
    reason: str = ""


@app.post("/users/{user_id}/balance", response_model=UserOut)
async def update_balance(
    user_id: int,
    data: BalanceUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    """Admin: add (positive) or subtract (negative) `amount` from user's balance."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.balance = float(user.balance or 0) + float(data.amount)
    db.add(ActivityLogModel(
        user_id=user.id,
        action="balance_adjusted",
        target=f"user:{user.id}",
        detail=f"amount={data.amount}; reason={data.reason}",
    ))
    db.commit()
    db.refresh(user)
    await publish_event(f"room:user_{user.id}", {
        "type": "balance_updated",
        "user_id": user.id,
        "balance": float(user.balance),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _user_out(user)


# ── Procurement extended actions ─────────────────────────────────────────────
@app.get("/procurements/{proc_id}/receipt")
def procurement_receipt(proc_id: int, db: Session = Depends(get_db), _: UserModel = Depends(current_user)):
    """Receipt / summary of a procurement: totals, per-participant rows, commission."""
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    participants = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.is_active.is_(True),
    ).all()
    rows = [_participant_out(pt) for pt in participants]
    total_quantity = sum(float(pt.quantity or 0) for pt in participants)
    total_amount = sum(float(pt.amount or 0) for pt in participants)
    commission = total_amount * float(p.commission_percent or 0) / 100.0
    return {
        "procurement_id": p.id,
        "title": p.title,
        "status": p.status,
        "participants": rows,
        "participant_count": len(rows),
        "total_quantity": total_quantity,
        "total_amount": total_amount,
        "commission_percent": float(p.commission_percent or 0),
        "commission_amount": commission,
        "grand_total": total_amount + commission,
    }


class StopAmountRequest(BaseModel):
    stop_at_amount: float


@app.post("/procurements/{proc_id}/stop-amount", response_model=ProcurementOut)
async def set_stop_amount(
    proc_id: int,
    data: StopAmountRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    p.stop_at_amount = data.stop_at_amount
    p.updated_at = datetime.now(timezone.utc)
    # Auto-stop if already reached
    if float(p.current_amount or 0) >= float(data.stop_at_amount):
        p.status = "stopped"
    db.commit()
    db.refresh(p)
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "stop_amount_updated",
        "procurement_id": p.id,
        "stop_at_amount": float(p.stop_at_amount),
        "status": p.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _procurement_out(p)


class ApproveSupplierRequest(BaseModel):
    supplier_name: str
    price_per_unit: Optional[float] = None


@app.post("/procurements/{proc_id}/approve-supplier", response_model=ProcurementOut)
async def approve_supplier(
    proc_id: int,
    data: ApproveSupplierRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    if data.price_per_unit is not None:
        p.price_per_unit = data.price_per_unit
    p.status = "payment"
    p.updated_at = datetime.now(timezone.utc)
    db.add(ActivityLogModel(
        user_id=user.id,
        action="supplier_approved",
        target=f"procurement:{p.id}",
        detail=f"supplier={data.supplier_name}; price={data.price_per_unit}",
    ))
    db.commit()
    db.refresh(p)
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "supplier_approved",
        "procurement_id": p.id,
        "supplier_name": data.supplier_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _procurement_out(p)


class CloseProcurementRequest(BaseModel):
    status: str = "completed"  # completed | cancelled


@app.post("/procurements/{proc_id}/close", response_model=ProcurementOut)
async def close_procurement(
    proc_id: int,
    data: CloseProcurementRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    if data.status not in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")
    p.status = data.status
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "procurement_closed",
        "procurement_id": p.id,
        "status": p.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _procurement_out(p)


# ── Voting ───────────────────────────────────────────────────────────────────
class VoteCreate(BaseModel):
    option: str


class VoteOut(BaseModel):
    id: int
    procurement_id: int
    user_id: int
    option: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.post("/procurements/{proc_id}/votes", response_model=VoteOut, status_code=201)
async def cast_vote(
    proc_id: int,
    data: VoteCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    # Only participants can vote (organizer allowed too)
    if p.organizer_id != user.id:
        is_participant = db.query(ParticipantModel).filter(
            ParticipantModel.procurement_id == proc_id,
            ParticipantModel.user_id == user.id,
            ParticipantModel.is_active.is_(True),
        ).first()
        if not is_participant:
            raise HTTPException(status_code=403, detail="Not a participant")
    existing = db.query(VoteModel).filter(
        VoteModel.procurement_id == proc_id,
        VoteModel.user_id == user.id,
    ).first()
    if existing:
        existing.option = data.option
        existing.created_at = datetime.now(timezone.utc)
        vote = existing
    else:
        vote = VoteModel(procurement_id=proc_id, user_id=user.id, option=data.option)
        db.add(vote)
    db.commit()
    db.refresh(vote)
    await publish_event(f"room:procurement_{proc_id}", {
        "type": "vote_cast",
        "procurement_id": proc_id,
        "user_id": user.id,
        "option": data.option,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return vote


@app.get("/procurements/{proc_id}/votes")
def vote_results(proc_id: int, db: Session = Depends(get_db), _: UserModel = Depends(current_user)):
    votes = db.query(VoteModel).filter(VoteModel.procurement_id == proc_id).all()
    tally: dict[str, int] = {}
    for v in votes:
        tally[v.option] = tally.get(v.option, 0) + 1
    winner = max(tally.items(), key=lambda kv: kv[1])[0] if tally else None
    return {
        "procurement_id": proc_id,
        "total_votes": len(votes),
        "tally": tally,
        "winner": winner,
    }


# ── Invitations ──────────────────────────────────────────────────────────────
class InvitationCreate(BaseModel):
    invitee_id: int


class InvitationOut(BaseModel):
    id: int
    procurement_id: int
    inviter_id: int
    invitee_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.post("/procurements/{proc_id}/invitations", response_model=InvitationOut, status_code=201)
async def invite_user(
    proc_id: int,
    data: InvitationCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    invitee = db.query(UserModel).filter(UserModel.id == data.invitee_id).first()
    if not invitee:
        raise HTTPException(status_code=404, detail="Invitee not found")
    inv = InvitationModel(procurement_id=proc_id, inviter_id=user.id, invitee_id=invitee.id)
    db.add(inv)
    # also create a notification
    db.add(NotificationModel(
        user_id=invitee.id,
        kind="invitation",
        title=f"Invitation: {p.title}",
        body=f"{user.username} invited you to procurement '{p.title}'",
        link=f"/procurements/{p.id}",
    ))
    db.commit()
    db.refresh(inv)
    await publish_event(f"room:user_{invitee.id}", {
        "type": "invitation_received",
        "procurement_id": proc_id,
        "procurement_title": p.title,
        "inviter": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return inv


@app.get("/invitations", response_model=list[InvitationOut])
def my_invitations(db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    return db.query(InvitationModel).filter(
        InvitationModel.invitee_id == user.id,
    ).order_by(InvitationModel.created_at.desc()).all()


@app.post("/invitations/{inv_id}/respond", response_model=InvitationOut)
async def respond_invitation(
    inv_id: int,
    accept: bool = Query(...),
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    inv = db.query(InvitationModel).filter(InvitationModel.id == inv_id).first()
    if not inv or inv.invitee_id != user.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    inv.status = "accepted" if accept else "declined"
    db.commit()
    db.refresh(inv)
    return inv


# ── Notifications ────────────────────────────────────────────────────────────
class NotificationOut(BaseModel):
    id: int
    user_id: int
    kind: str
    title: str
    body: str
    link: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    user_id: int
    kind: str = "system"
    title: str = ""
    body: str = ""
    link: str = ""


@app.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    q = db.query(NotificationModel).filter(NotificationModel.user_id == user.id)
    if unread_only:
        q = q.filter(NotificationModel.is_read.is_(False))
    return q.order_by(NotificationModel.created_at.desc()).limit(limit).all()


@app.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    from sqlalchemy import func
    c = db.query(func.count(NotificationModel.id)).filter(
        NotificationModel.user_id == user.id,
        NotificationModel.is_read.is_(False),
    ).scalar() or 0
    return {"count": int(c)}


@app.post("/notifications/{notif_id}/read", status_code=204)
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    n = db.query(NotificationModel).filter(NotificationModel.id == notif_id).first()
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()


@app.post("/notifications/mark-all-read", status_code=204)
def mark_all_notifications_read(db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    db.query(NotificationModel).filter(
        NotificationModel.user_id == user.id,
        NotificationModel.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()


@app.post("/notifications", response_model=NotificationOut, status_code=201)
async def send_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    n = NotificationModel(**data.model_dump())
    db.add(n)
    db.commit()
    db.refresh(n)
    await publish_event(f"room:user_{data.user_id}", {
        "type": "notification",
        "notification_id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return n


# ── Chat: send message via REST (fallback when no socket) / mark read ────────
class ChatMessageCreate(BaseModel):
    text: str


@app.post("/chat/{room}/messages", response_model=ChatMessageOut, status_code=201)
async def post_chat_message(
    room: str,
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    text_ = (data.text or "").strip()
    if not text_:
        raise HTTPException(status_code=400, detail="Empty message")
    msg = ChatMessageModel(
        room=room,
        user_id=user.id,
        msg_type="message",
        text=text_[:2000],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    await publish_event(f"room:{room}", {
        "type": "message",
        "room": room,
        "user_id": str(user.id),
        "text": msg.text,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else datetime.now(timezone.utc).isoformat(),
    })
    return _chat_msg_out(msg)


@app.post("/chat/{room}/mark-read", status_code=204)
def mark_room_read(
    room: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    msgs = db.query(ChatMessageModel).filter(ChatMessageModel.room == room).all()
    uid = str(user.id)
    for m in msgs:
        readers = set((m.read_by or "").split(",")) - {""}
        if uid not in readers:
            readers.add(uid)
            m.read_by = ",".join(sorted(readers))
    db.commit()


@app.get("/chat/{room}/unread-count")
def room_unread_count(
    room: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    msgs = db.query(ChatMessageModel).filter(ChatMessageModel.room == room).all()
    uid = str(user.id)
    count = 0
    for m in msgs:
        readers = set((m.read_by or "").split(",")) - {""}
        if uid not in readers and m.user_id != user.id:
            count += 1
    return {"room": room, "count": count}


# ── Reviews ──────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    target_user_id: int
    rating: int
    body: str = ""
    procurement_id: Optional[int] = None


class ReviewOut(BaseModel):
    id: int
    author_id: int
    author_username: str
    target_user_id: int
    procurement_id: Optional[int]
    rating: int
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(data: ReviewCreate, db: Session = Depends(get_db), user: UserModel = Depends(current_user)):
    if not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1..5")
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot review yourself")
    target = db.query(UserModel).filter(UserModel.id == data.target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")
    r = ReviewModel(
        author_id=user.id,
        target_user_id=data.target_user_id,
        procurement_id=data.procurement_id,
        rating=data.rating,
        body=data.body,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _review_out(r)


@app.get("/users/{user_id}/reviews", response_model=list[ReviewOut])
def user_reviews(user_id: int, db: Session = Depends(get_db)):
    rs = db.query(ReviewModel).filter(ReviewModel.target_user_id == user_id) \
        .order_by(ReviewModel.created_at.desc()).all()
    return [_review_out(r) for r in rs]


@app.get("/users/{user_id}/rating")
def user_rating(user_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func
    avg = db.query(func.avg(ReviewModel.rating)).filter(ReviewModel.target_user_id == user_id).scalar()
    count = db.query(func.count(ReviewModel.id)).filter(ReviewModel.target_user_id == user_id).scalar() or 0
    return {"user_id": user_id, "average": float(avg) if avg else None, "count": int(count)}


# ── Complaints ───────────────────────────────────────────────────────────────
class ComplaintCreate(BaseModel):
    subject: str
    body: str
    target_user_id: Optional[int] = None
    procurement_id: Optional[int] = None


class ComplaintUpdate(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None


class ComplaintOut(BaseModel):
    id: int
    reporter_id: int
    reporter_username: str
    target_user_id: Optional[int]
    procurement_id: Optional[int]
    subject: str
    body: str
    status: str
    resolution: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@app.post("/complaints", response_model=ComplaintOut, status_code=201)
async def create_complaint(
    data: ComplaintCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    c = ComplaintModel(
        reporter_id=user.id,
        target_user_id=data.target_user_id,
        procurement_id=data.procurement_id,
        subject=data.subject,
        body=data.body,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    await publish_event("room:admin", {
        "type": "complaint_filed",
        "complaint_id": c.id,
        "reporter": user.username,
        "subject": c.subject,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _complaint_out(c)


@app.get("/complaints", response_model=list[ComplaintOut])
def list_complaints(
    status_filter: Optional[str] = Query(None, alias="status"),
    mine: bool = False,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    q = db.query(ComplaintModel)
    if mine or not user.is_admin:
        q = q.filter(ComplaintModel.reporter_id == user.id)
    if status_filter:
        q = q.filter(ComplaintModel.status == status_filter)
    return [_complaint_out(c) for c in q.order_by(ComplaintModel.created_at.desc()).all()]


@app.patch("/complaints/{cid}", response_model=ComplaintOut)
async def update_complaint(
    cid: int,
    data: ComplaintUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    c = db.query(ComplaintModel).filter(ComplaintModel.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(c)
    await publish_event(f"room:user_{c.reporter_id}", {
        "type": "complaint_updated",
        "complaint_id": c.id,
        "status": c.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return _complaint_out(c)


# ── Admin: analytics, broadcast, featured, activity log ──────────────────────
@app.get("/admin/analytics")
def admin_analytics(db: Session = Depends(get_db), _: UserModel = Depends(admin_user)):
    from sqlalchemy import func
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=30)

    new_users_30d = db.query(func.count(UserModel.id)).filter(
        UserModel.created_at >= past
    ).scalar() or 0
    new_procurements_30d = db.query(func.count(ProcurementModel.id)).filter(
        ProcurementModel.created_at >= past
    ).scalar() or 0

    # Status breakdown
    status_rows = db.query(ProcurementModel.status, func.count(ProcurementModel.id)) \
        .group_by(ProcurementModel.status).all()
    status_breakdown = {s: int(c) for s, c in status_rows}

    # Payment totals by type
    type_rows = db.query(PaymentModel.payment_type, func.sum(PaymentModel.amount)) \
        .filter(PaymentModel.status == "succeeded") \
        .group_by(PaymentModel.payment_type).all()
    payments_by_type = {t: float(a or 0) for t, a in type_rows}

    # Top cities
    city_rows = db.query(ProcurementModel.city, func.count(ProcurementModel.id)) \
        .filter(ProcurementModel.city != "") \
        .group_by(ProcurementModel.city) \
        .order_by(func.count(ProcurementModel.id).desc()).limit(5).all()
    top_cities = [{"city": c, "count": int(n)} for c, n in city_rows]

    # Top participants
    part_rows = db.query(ParticipantModel.user_id, func.count(ParticipantModel.id)) \
        .filter(ParticipantModel.is_active.is_(True)) \
        .group_by(ParticipantModel.user_id) \
        .order_by(func.count(ParticipantModel.id).desc()).limit(5).all()
    top_users_ids = [uid for uid, _n in part_rows]
    users_map = {
        u.id: u.username
        for u in db.query(UserModel).filter(UserModel.id.in_(top_users_ids)).all()
    } if top_users_ids else {}
    top_participants = [
        {"user_id": uid, "username": users_map.get(uid, str(uid)), "count": int(n)}
        for uid, n in part_rows
    ]

    open_complaints = db.query(func.count(ComplaintModel.id)).filter(
        ComplaintModel.status == "open"
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),
        "window_days": 30,
        "new_users_30d": int(new_users_30d),
        "new_procurements_30d": int(new_procurements_30d),
        "status_breakdown": status_breakdown,
        "payments_by_type": payments_by_type,
        "top_cities": top_cities,
        "top_participants": top_participants,
        "open_complaints": int(open_complaints),
    }


class BroadcastRequest(BaseModel):
    title: str
    body: str
    link: str = ""
    kind: str = "system"


@app.post("/admin/broadcast")
async def admin_broadcast(
    data: BroadcastRequest,
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    """Send a notification to every active user. Returns the number of recipients."""
    users = db.query(UserModel).filter(UserModel.is_active.is_(True)).all()
    for u in users:
        db.add(NotificationModel(
            user_id=u.id,
            kind=data.kind,
            title=data.title,
            body=data.body,
            link=data.link,
        ))
    db.commit()
    # Publish per-user events
    for u in users:
        await publish_event(f"room:user_{u.id}", {
            "type": "notification",
            "kind": data.kind,
            "title": data.title,
            "body": data.body,
            "link": data.link,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return {"sent": len(users)}


@app.post("/procurements/{proc_id}/toggle-featured", response_model=ProcurementOut)
async def toggle_featured(
    proc_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    p.is_featured = not p.is_featured
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return _procurement_out(p)


@app.get("/admin/activity-log")
def admin_activity_log(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: UserModel = Depends(admin_user),
):
    rows = db.query(ActivityLogModel).order_by(ActivityLogModel.created_at.desc()).limit(limit).all()
    users_map = {u.id: u.username for u in db.query(UserModel).all()}
    return [{
        "id": r.id,
        "user_id": r.user_id,
        "username": users_map.get(r.user_id, "") if r.user_id else "",
        "action": r.action,
        "target": r.target,
        "detail": r.detail,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


# ── Search ───────────────────────────────────────────────────────────────────
@app.get("/search/procurements", response_model=list[ProcurementOut])
def search_procurements(
    q: str = Query("", min_length=0),
    city: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Full-text search across procurement title and description."""
    query = db.query(ProcurementModel)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (ProcurementModel.title.ilike(like)) | (ProcurementModel.description.ilike(like))
        )
    if city:
        query = query.filter(ProcurementModel.city.ilike(f"%{city}%"))
    if category_id:
        query = query.filter(ProcurementModel.category_id == category_id)
    if status:
        query = query.filter(ProcurementModel.status == status)
    return [_procurement_out(p) for p in query.order_by(ProcurementModel.created_at.desc()).limit(limit).all()]


# ── Output helpers (avoids Pydantic issues with Decimal/lazy-load) ────────────
def _user_out(u: UserModel) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "phone": u.phone or "",
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


def _review_out(r: ReviewModel) -> dict:
    return {
        "id": r.id,
        "author_id": r.author_id,
        "author_username": r.author.username if r.author else "",
        "target_user_id": r.target_user_id,
        "procurement_id": r.procurement_id,
        "rating": r.rating,
        "body": r.body or "",
        "created_at": r.created_at,
    }


def _complaint_out(c: ComplaintModel) -> dict:
    return {
        "id": c.id,
        "reporter_id": c.reporter_id,
        "reporter_username": c.reporter.username if c.reporter else "",
        "target_user_id": c.target_user_id,
        "procurement_id": c.procurement_id,
        "subject": c.subject or "",
        "body": c.body or "",
        "status": c.status,
        "resolution": c.resolution or "",
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }
