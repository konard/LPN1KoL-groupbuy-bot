from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import create_token, hash_password, verify_password
from app.models.models import UserModel
from app.services.auth_service import current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    balance: float

    class Config:
        from_attributes = True


@router.post("/register", response_model=UserOut, status_code=201)
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
    return {"id": user.id, "username": user.username, "email": user.email,
            "is_active": user.is_active, "is_admin": user.is_admin,
            "balance": float(user.balance or 0)}


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return {"access_token": create_token({"sub": str(user.id)})}


@router.get("/me", response_model=UserOut)
def me(user: UserModel = Depends(current_user)):
    return {"id": user.id, "username": user.username, "email": user.email,
            "is_active": user.is_active, "is_admin": user.is_admin,
            "balance": float(user.balance or 0)}
