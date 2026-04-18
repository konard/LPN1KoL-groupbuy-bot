import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PurchaseCreate(BaseModel):
    title: str
    description: str | None = None
    target_amount: Decimal
    commission_pct: Decimal = Decimal("0")


class PurchaseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    organizer_id: uuid.UUID
    status: str
    target_amount: Decimal
    current_amount: Decimal
    commission_pct: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteCreate(BaseModel):
    value: int = 1


class VoteOut(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    user_id: uuid.UUID
    value: int
    created_at: datetime

    model_config = {"from_attributes": True}
