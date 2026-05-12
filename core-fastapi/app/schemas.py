"""Pydantic schemas for all core resources."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str = "core"


class ErrorDetail(BaseModel):
    """Standard error response envelope used by HTTPException."""

    detail: Any = Field(..., description="Human-readable error message or per-field validation details")


class ExistsResponse(BaseModel):
    """Boolean existence check returned by /api/users/check_exists/."""

    exists: bool


class MessageResponse(BaseModel):
    """Single-field acknowledgement (e.g. session cleared)."""

    message: str


class BalanceUpdateResponse(BaseModel):
    """Response returned by POST /api/users/{id}/update_balance/."""

    balance: Decimal
    message: str


class UserRoleResponse(BaseModel):
    """Response returned by GET /api/users/{id}/role/."""

    role: str
    role_display: str


class WsTokenResponse(BaseModel):
    """JWT token returned by GET /api/users/{id}/ws_token/."""

    token: str
    expires_in: int


# ─── User schemas ─────────────────────────────────────────────────────────────

class CreateUser(BaseModel):
    # Optional explicit UUID — auth-service uses this to keep its own user.id
    # in sync with core's users.id, so frontend calls like
    # /api/users/{auth-uuid}/balance/ resolve without a separate id lookup.
    id: UUID | None = None
    platform: str | None = "telegram"
    platform_user_id: str
    username: str | None = ""
    first_name: str | None = ""
    last_name: str | None = ""
    phone: str | None = ""
    email: str | None = ""
    role: str | None = "buyer"
    language_code: str | None = "ru"
    selfie_file_id: str | None = ""


class UpdateUser(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str | None = None


class UserResponse(BaseModel):
    id: UUID
    platform: str
    platform_user_id: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    email: str
    role: str
    role_display: str
    balance: Decimal
    language_code: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserBalanceResponse(BaseModel):
    balance: Decimal
    total_deposited: Decimal
    total_spent: Decimal
    available: Decimal


class UpdateBalanceRequest(BaseModel):
    amount: float


class SetSessionState(BaseModel):
    user_id: UUID
    dialog_type: str | None = ""
    dialog_state: str | None = ""
    dialog_data: Any | None = None


class ClearSessionRequest(BaseModel):
    user_id: UUID


# ─── Procurement schemas ──────────────────────────────────────────────────────

class CreateProcurement(BaseModel):
    title: str
    description: str = ""
    category_id: int | None = None
    organizer_id: UUID
    city: str = ""
    delivery_address: str | None = ""
    target_amount: Decimal
    stop_at_amount: Decimal | None = None
    unit: str | None = "units"
    price_per_unit: Decimal | None = None
    status: str | None = "draft"
    commission_percent: Decimal | None = Decimal("0")
    min_quantity: Decimal | None = None
    deadline: datetime
    payment_deadline: datetime | None = None
    image_url: str | None = ""


class JoinProcurement(BaseModel):
    user_id: UUID | None = None
    amount: Decimal
    quantity: Decimal | None = Decimal("1")
    notes: str | None = ""


class ProcurementResponse(BaseModel):
    id: int
    title: str
    description: str
    category_id: int | None
    organizer_id: UUID
    supplier_id: UUID | None
    city: str
    delivery_address: str
    target_amount: Decimal
    current_amount: Decimal
    stop_at_amount: Decimal | None
    unit: str
    price_per_unit: Decimal | None
    status: str
    status_display: str
    commission_percent: Decimal
    min_quantity: Decimal | None
    deadline: datetime
    payment_deadline: datetime | None
    image_url: str
    is_featured: bool
    progress: int
    participant_count: int
    days_left: int
    can_join: bool
    created_at: datetime
    updated_at: datetime


# ─── Payment schemas ──────────────────────────────────────────────────────────

class CreatePayment(BaseModel):
    user_id: UUID
    payment_type: str
    amount: Decimal
    procurement_id: int | None = None
    description: str | None = ""


class PaymentStatusResponse(BaseModel):
    id: int
    status: str
    status_display: str
    amount: Decimal
    confirmation_url: str


# ─── Chat schemas ─────────────────────────────────────────────────────────────

class CreateMessage(BaseModel):
    procurement: int
    user: UUID | None = None
    text: str
    message_type: str | None = "text"
    attachment_url: str | None = ""


# ─── Buyer request schemas ────────────────────────────────────────────────────

class CreateBuyerRequest(BaseModel):
    user_id: UUID
    product_name: str
    quantity: Decimal | None = Decimal("1")
    unit: str | None = "units"
    city: str | None = ""
    notes: str | None = ""


class UpdateBuyerRequest(BaseModel):
    product_name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    city: str | None = None
    notes: str | None = None
    is_active: bool | None = None


# ─── News schemas ─────────────────────────────────────────────────────────────

class CreateNewsPost(BaseModel):
    author_id: UUID
    title: str
    content: str = ""


class UpdateNewsPost(BaseModel):
    title: str | None = None
    content: str | None = None


# ─── Poll schemas ─────────────────────────────────────────────────────────────

class CreatePoll(BaseModel):
    author_id: UUID
    procurement_id: int | None = None
    question: str
    options: list[str]
    poll_type: str | None = "general"


class CastVote(BaseModel):
    user_id: UUID
    option_id: int


# ─── Supplier company schemas ─────────────────────────────────────────────────

class UpsertSupplierCompany(BaseModel):
    user_id: UUID
    name: str
    legal_address: str = ""
    postal_address: str = ""
    actual_address: str = ""
    okved: str = ""
    ogrn: str = ""
    inn: str = ""
    contact_phone: str = ""
    email: str = ""
    is_published: bool = True


class UpsertPriceList(BaseModel):
    supplier_id: UUID
    file_url: str = ""
    popular_items: list[dict] | None = None
    is_published: bool = True


# ─── Invitation schemas ───────────────────────────────────────────────────────

class CreateInvitation(BaseModel):
    organizer_id: UUID
    invitee_id: UUID | None = None
    invitee_email: str = ""
    invitee_role: str = "supplier"
    procurement_id: int | None = None
    message: str = ""


class UpdateInvitationStatus(BaseModel):
    status: str  # one of: accepted, declined, cancelled


# ─── Closing document schemas ─────────────────────────────────────────────────

class CreateClosingDocument(BaseModel):
    procurement_id: int
    supplier_id: UUID
    file_url: str = ""
    comment: str = ""


# ─── Withdrawal schemas ───────────────────────────────────────────────────────

class CreateWithdrawal(BaseModel):
    user_id: UUID
    amount: Decimal
    bank_details: str = ""


# ─── Procurement lifecycle schemas ────────────────────────────────────────────

class ApproveSupplier(BaseModel):
    supplier_id: UUID
