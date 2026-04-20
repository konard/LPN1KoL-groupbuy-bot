import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    platform: str = "websocket"
    platform_user_id: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    role: str = "buyer"
    language_code: str = "ru"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    totp_enabled: bool
    platform: str
    platform_user_id: str | None
    username: str | None
    first_name: str | None
    last_name: str | None
    phone: str | None
    role: str
    balance: Decimal
    is_verified: bool
    is_banned: bool
    language_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    role: str | None = None
    language_code: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class UserBalanceOut(BaseModel):
    balance: Decimal
    total_deposited: Decimal
    total_spent: Decimal
    available: Decimal


class UpdateBalanceRequest(BaseModel):
    amount: Decimal


class WsTokenResponse(BaseModel):
    token: str
    expires_in: int


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_uri: str


class TOTPVerifyRequest(BaseModel):
    code: str
