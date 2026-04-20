import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
    icon: str | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    parent_id: uuid.UUID | None
    icon: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Purchase / Procurement ────────────────────────────────────────────────────

class PurchaseCreate(BaseModel):
    title: str
    description: str | None = None
    target_amount: Decimal
    commission_pct: Decimal = Decimal("0")
    category_id: uuid.UUID | None = None
    city: str | None = None
    delivery_address: str | None = None
    stop_at_amount: Decimal | None = None
    unit: str = "units"
    price_per_unit: Decimal | None = None
    min_quantity: Decimal | None = None
    deadline: datetime | None = None
    image_url: str | None = None


class PurchaseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    organizer_id: uuid.UUID
    supplier_id: uuid.UUID | None
    category_id: uuid.UUID | None
    city: str | None
    status: str
    target_amount: Decimal
    current_amount: Decimal
    stop_at_amount: Decimal | None
    commission_pct: Decimal
    unit: str
    price_per_unit: Decimal | None
    deadline: datetime | None
    image_url: str | None
    is_featured: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseStatusUpdate(BaseModel):
    status: str


# ── Votes / Supplier selection ────────────────────────────────────────────────

class VoteCreate(BaseModel):
    value: int = 1
    candidate_id: uuid.UUID | None = None


class VoteOut(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    user_id: uuid.UUID
    value: int
    candidate_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteResultOut(BaseModel):
    candidate_id: uuid.UUID | None
    total_votes: int
    total_value: int


class ApproveSupplierRequest(BaseModel):
    supplier_id: uuid.UUID


# ── Participants ──────────────────────────────────────────────────────────────

class JoinPurchaseRequest(BaseModel):
    quantity: Decimal = Decimal("1")
    amount: Decimal
    notes: str | None = None


class ParticipantOut(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    quantity: Decimal
    amount: Decimal
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
