import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Электронная почта пользователя", json_schema_extra={"example": "user@example.com"})
    password: str = Field(..., min_length=1, description="Пароль пользователя (любой непустой)", json_schema_extra={"example": "securepassword123"})
    platform: str = Field("websocket", description="Платформа (telegram, websocket и т.д.)")
    platform_user_id: str | None = Field(None, description="Идентификатор пользователя на платформе")
    username: str | None = Field(None, description="Имя пользователя (никнейм)")
    first_name: str | None = Field(None, description="Имя")
    last_name: str | None = Field(None, description="Фамилия")
    phone: str | None = Field(None, description="Контактный телефон")
    role: str = Field("buyer", description="Роль пользователя: buyer | organizer | supplier", json_schema_extra={"example": "buyer"})
    language_code: str = Field("ru", description="Код языка интерфейса")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "role": "buyer",
                "first_name": "Иван",
                "last_name": "Иванов",
            }
        }
    }


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Электронная почта пользователя", json_schema_extra={"example": "user@example.com"})
    password: str = Field(..., min_length=1, description="Пароль пользователя (любой непустой)", json_schema_extra={"example": "securepassword123"})
    totp_code: str | None = Field(None, description="Код двухфакторной аутентификации (если включена)", json_schema_extra={"example": "123456"})

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
            }
        }
    }


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access-токен")
    refresh_token: str = Field(..., description="JWT refresh-токен")
    token_type: str = Field("bearer", description="Тип токена")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    }


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Действующий refresh-токен")

    model_config = {
        "json_schema_extra": {
            "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }
    }


class UserOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор пользователя")
    email: str = Field(..., description="Электронная почта")
    is_active: bool = Field(..., description="Аккаунт активен")
    totp_enabled: bool = Field(..., description="Двухфакторная аутентификация включена")
    platform: str = Field(..., description="Платформа пользователя")
    platform_user_id: str | None = Field(None, description="Идентификатор на платформе")
    username: str | None = Field(None, description="Никнейм пользователя")
    first_name: str | None = Field(None, description="Имя")
    last_name: str | None = Field(None, description="Фамилия")
    phone: str | None = Field(None, description="Контактный телефон")
    role: str = Field(..., description="Роль: buyer | organizer | supplier")
    balance: Decimal = Field(..., description="Баланс пользователя")
    is_verified: bool = Field(..., description="Аккаунт верифицирован")
    is_banned: bool = Field(..., description="Аккаунт заблокирован")
    language_code: str = Field(..., description="Код языка интерфейса")
    created_at: datetime = Field(..., description="Дата регистрации")

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: str | None = Field(None, description="Никнейм пользователя")
    first_name: str | None = Field(None, description="Имя")
    last_name: str | None = Field(None, description="Фамилия")
    phone: str | None = Field(None, description="Контактный телефон")
    role: str | None = Field(None, description="Роль: buyer | organizer | supplier")
    language_code: str | None = Field(None, description="Код языка")
    is_active: bool | None = Field(None, description="Статус активности аккаунта")
    is_verified: bool | None = Field(None, description="Статус верификации")


class UserBalanceOut(BaseModel):
    balance: Decimal = Field(..., description="Текущий баланс")
    total_deposited: Decimal = Field(..., description="Всего пополнено")
    total_spent: Decimal = Field(..., description="Всего потрачено (заблокировано)")
    available: Decimal = Field(..., description="Доступный баланс")

    model_config = {
        "json_schema_extra": {
            "example": {
                "balance": "1500.00",
                "total_deposited": "1500.00",
                "total_spent": "200.00",
                "available": "1300.00",
            }
        }
    }


class UpdateBalanceRequest(BaseModel):
    amount: Decimal = Field(..., description="Сумма изменения баланса (положительная — пополнение, отрицательная — списание)", json_schema_extra={"example": "500.00"})

    model_config = {
        "json_schema_extra": {"example": {"amount": "500.00"}}
    }


class WsTokenResponse(BaseModel):
    token: str = Field(..., description="WebSocket JWT-токен")
    expires_in: int = Field(..., description="Срок действия токена в секундах")

    model_config = {
        "json_schema_extra": {
            "example": {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "expires_in": 86400}
        }
    }


class TOTPSetupResponse(BaseModel):
    secret: str = Field(..., description="TOTP-секрет для ручного ввода")
    qr_uri: str = Field(..., description="URI для QR-кода (otpauth://...)")


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="6-значный TOTP-код", json_schema_extra={"example": "123456"})
