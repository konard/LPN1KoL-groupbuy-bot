import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class WalletOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    balance: Decimal
    hold_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class DepositRequest(BaseModel):
    amount: Decimal


class HoldRequest(BaseModel):
    amount: Decimal


class EscrowCreate(BaseModel):
    purchase_id: uuid.UUID
    amount: Decimal


class EscrowOut(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    payer_id: uuid.UUID
    amount: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
