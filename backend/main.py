import os
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ── Config ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

# ── Database ─────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="GroupBuy Backend API", version="1.0.0")

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
    return user


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
    return user


# ── User CRUD (admin) ─────────────────────────────────────────────────────────
@app.get("/users", response_model=list[UserOut])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _=Depends(admin_user)):
    return db.query(UserModel).offset(skip).limit(limit).all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


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
def receive_socket_event(event: SocketEvent):
    # Persist or process real-time events sent by the socket service.
    # Currently logs; extend to store messages in DB as needed.
    return None
