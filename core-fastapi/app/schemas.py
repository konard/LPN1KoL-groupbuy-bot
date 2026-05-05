"""Pydantic schemas for the example `products` resource."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    price_cents: int = Field(ge=0, default=0)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)


class Product(ProductBase):
    id: int
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str = "core"
