from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import (
    create_token,
    get_current_user,
    get_token_payload,
)
from security import verify_password
from config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from database import get_db
from models import UserModel
from repositories import LogRepository, UserRepository
from schemas import LoginResponse, RefreshRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_username(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверные учётные данные")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    access = create_token(
        {"sub": str(user.id), "role": user.role},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh = create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    LogRepository(db).create(user.id, "login", f"username={user.username}")
    return LoginResponse(access_token=access, refresh_token=refresh, role=user.role)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = get_token_payload(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Токен не является refresh-токеном")
    user_id = payload.get("sub")
    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден или неактивен")
    access = create_token(
        {"sub": str(user.id), "role": user.role},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=access)


@router.get("/me", response_model=UserOut)
def me(user: UserModel = Depends(get_current_user)):
    return user
