"""
Роутер аутентификации (/api/auth/*).
Перенесён из auth-service (порт 4001).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Регистрация нового пользователя."""
    user = register_user(db, data.username, data.email, data.password, data.phone)
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Вход по логину и паролю. Возвращает access + refresh токены."""
    access_token, refresh_token = authenticate_user(db, data.username, data.password, data.totp_code)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    """Возвращает профиль текущего авторизованного пользователя."""
    return user
