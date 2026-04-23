import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BuyerRequestCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255, description="Название товара", example="Мука пшеничная высший сорт")
    quantity: str = Field(..., min_length=1, max_length=100, description="Количество товара (с единицами измерения)", example="50 кг")
    city: str = Field(..., min_length=1, max_length=100, description="Город получения товара", example="Москва")
    notes: str | None = Field(None, description="Примечание (предпочтения по бренду, срокам и т.д.)", example="Предпочтительно марки «Нордик»")

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_name": "Мука пшеничная высший сорт",
                "quantity": "50 кг",
                "city": "Москва",
                "notes": "Предпочтительно марки «Нордик»",
            }
        }
    }


class BuyerRequestUpdate(BaseModel):
    product_name: str | None = Field(None, min_length=1, max_length=255, description="Название товара")
    quantity: str | None = Field(None, min_length=1, max_length=100, description="Количество товара")
    city: str | None = Field(None, min_length=1, max_length=100, description="Город получения товара")
    notes: str | None = Field(None, description="Примечание")


class BuyerRequestOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор запроса")
    buyer_id: uuid.UUID = Field(..., description="Идентификатор покупателя")
    product_name: str = Field(..., description="Название товара")
    quantity: str = Field(..., description="Количество товара")
    city: str = Field(..., description="Город получения товара")
    notes: str | None = Field(None, description="Примечание")
    is_active: bool = Field(..., description="Запрос активен")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "buyer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "product_name": "Мука пшеничная высший сорт",
                "quantity": "50 кг",
                "city": "Москва",
                "notes": "Предпочтительно марки «Нордик»",
                "is_active": True,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
            }
        },
    }
