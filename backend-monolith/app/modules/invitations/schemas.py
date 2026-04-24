import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class InviteSupplierRequest(BaseModel):
    email: EmailStr = Field(..., description="Электронная почта поставщика для отправки приглашения", example="supplier@example.com")
    message: str | None = Field(None, description="Текст приглашения", example="Приглашаем вас принять участие в нашей закупке.")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор закупки (необязательно)", example="3fa85f64-5717-4562-b3fc-2c963f66afa6")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "supplier@example.com",
                "message": "Приглашаем вас принять участие в нашей закупке.",
                "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            }
        }
    }


class InviteBuyerRequest(BaseModel):
    message: str | None = Field(None, description="Текст приглашения для покупателей", example="Присоединяйтесь к нашей закупке!")
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки", example="3fa85f64-5717-4562-b3fc-2c963f66afa6")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Присоединяйтесь к нашей закупке!",
                "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            }
        }
    }


class InvitationOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор приглашения")
    sender_id: uuid.UUID = Field(..., description="Идентификатор отправителя")
    recipient_email: str | None = Field(None, description="Email получателя (для поставщиков)")
    recipient_id: uuid.UUID | None = Field(None, description="Идентификатор получателя (для покупателей)")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор закупки")
    invitation_type: str = Field(..., description="Тип приглашения: supplier | buyer")
    message: str | None = Field(None, description="Текст приглашения")
    status: str = Field(..., description="Статус: pending | accepted | declined")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "sender_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "recipient_email": "supplier@example.com",
                "recipient_id": None,
                "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
                "invitation_type": "supplier",
                "message": "Приглашаем вас принять участие в нашей закупке.",
                "status": "pending",
                "created_at": "2024-01-01T12:00:00Z",
            }
        },
    }
