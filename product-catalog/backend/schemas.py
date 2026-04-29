from typing import Optional

from pydantic import BaseModel

from models import UserRole


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryIn(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class ProductIn(BaseModel):
    name: str
    description: str = ""
    price_rub: float
    general_note: str = ""
    special_note: str = ""
    category_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_rub: Optional[float] = None
    general_note: Optional[str] = None
    special_note: Optional[str] = None
    category_id: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    price_rub: float
    general_note: str
    special_note: str
    category_id: int
    category_name: str

    model_config = {"from_attributes": True}


class ProductOutSimple(BaseModel):
    id: int
    name: str
    description: str
    price_rub: float
    general_note: str
    category_id: int
    category_name: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole


class PasswordChange(BaseModel):
    new_password: str


class UsdConversion(BaseModel):
    price_rub: float
    price_usd: float
    rate: float
