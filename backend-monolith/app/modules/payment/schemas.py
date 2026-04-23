import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class WalletOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор кошелька")
    user_id: uuid.UUID = Field(..., description="Идентификатор пользователя")
    balance: Decimal = Field(..., description="Текущий баланс")
    hold_amount: Decimal = Field(..., description="Заблокированная сумма")
    created_at: datetime = Field(..., description="Дата создания кошелька")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "balance": "1500.00",
                "hold_amount": "200.00",
                "created_at": "2024-01-01T12:00:00Z",
            }
        },
    }


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма пополнения баланса", example="500.00")
    payment_method: str | None = Field(None, description="Способ оплаты (банковская карта, электронный кошелёк и т.д.)", example="Банковская карта")

    model_config = {
        "json_schema_extra": {
            "example": {"amount": "500.00", "payment_method": "Банковская карта"}
        }
    }


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма для вывода средств", example="300.00")
    account_details: str = Field(..., min_length=1, description="Реквизиты счёта для перевода средств", example="Карта Сбербанк: 4276 1234 5678 9012")

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": "300.00",
                "account_details": "Карта Сбербанк: 4276 1234 5678 9012",
            }
        }
    }


class HoldRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма для блокировки (резервирования)", example="200.00")

    model_config = {
        "json_schema_extra": {"example": {"amount": "200.00"}}
    }


class EscrowCreate(BaseModel):
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки")
    amount: Decimal = Field(..., gt=0, description="Сумма эскроу")

    model_config = {
        "json_schema_extra": {
            "example": {"purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "amount": "500.00"}
        }
    }


class EscrowOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор эскроу")
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки")
    payer_id: uuid.UUID = Field(..., description="Идентификатор плательщика")
    amount: Decimal = Field(..., description="Сумма эскроу")
    status: str = Field(..., description="Статус эскроу")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "payer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
                "amount": "500.00",
                "status": "held",
                "created_at": "2024-01-01T12:00:00Z",
            }
        },
    }
