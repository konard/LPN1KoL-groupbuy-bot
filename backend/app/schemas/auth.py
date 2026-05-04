"""
Pydantic-схемы для модуля аутентификации.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Запрос регистрации нового пользователя."""
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    """Запрос входа по логину/паролю. Поддерживает TOTP."""
    username: str
    password: str
    totp_code: Optional[str] = None


class RefreshRequest(BaseModel):
    """Обновление access-токена по refresh-токену."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Ответ с парой токенов."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Публичные данные пользователя."""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool
    is_verified: bool
    totp_enabled: bool
    balance: float
    reputation_score: float
    is_blocked: bool
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
