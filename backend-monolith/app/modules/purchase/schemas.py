import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название категории", example="Продукты питания")
    description: str | None = Field(None, description="Описание категории")
    parent_id: uuid.UUID | None = Field(None, description="Идентификатор родительской категории")
    icon: str | None = Field(None, description="Иконка категории")

    model_config = {
        "json_schema_extra": {"example": {"name": "Продукты питания", "description": "Товары продовольственной группы", "parent_id": None, "icon": "🛒"}}
    }


class CategoryOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор категории")
    name: str = Field(..., description="Название категории")
    description: str | None = Field(None, description="Описание категории")
    parent_id: uuid.UUID | None = Field(None, description="Идентификатор родительской категории")
    icon: str | None = Field(None, description="Иконка категории")
    is_active: bool = Field(..., description="Категория активна")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = {"from_attributes": True}


# ── Purchase / Procurement ────────────────────────────────────────────────────

class PurchaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Название товара для закупки", example="Мука пшеничная высший сорт")
    description: str | None = Field(None, description="Описание закупки")
    target_amount: Decimal = Field(..., gt=0, description="Целевая сумма закупки", example="10000.00")
    commission_pct: Decimal = Field(Decimal("2"), ge=1, le=4, description="Комиссия организатора (от 1% до 4%)", example="2")
    category_id: uuid.UUID | None = Field(None, description="Идентификатор категории")
    city: str = Field(..., min_length=1, max_length=100, description="Город получения товара", example="Москва")
    delivery_address: str | None = Field(None, description="Адрес доставки")
    stop_at_amount: Decimal | None = Field(None, gt=0, description="Сумма остановки закупки (стоп-сумма)")
    unit: str = Field("штуки", min_length=1, max_length=20, description="Единица измерения товара", example="кг")
    price_per_unit: Decimal | None = Field(None, gt=0, description="Цена за единицу товара")
    min_quantity: Decimal | None = Field(None, gt=0, description="Минимальное количество товара для запуска закупки")
    deadline: datetime | None = Field(None, description="Срок окончания закупки")
    image_url: str | None = Field(None, description="Ссылка на изображение товара")

    @field_validator("commission_pct")
    @classmethod
    def validate_commission(cls, v: Decimal) -> Decimal:
        if v < 1 or v > 4:
            raise ValueError("Комиссия организатора должна быть от 1% до 4%")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Мука пшеничная высший сорт",
                "description": "Групповая закупка муки пшеничной высшего сорта",
                "target_amount": "10000.00",
                "commission_pct": "2",
                "city": "Москва",
                "unit": "кг",
                "min_quantity": "100",
            }
        }
    }


class PurchaseOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор закупки")
    title: str = Field(..., description="Название товара")
    description: str | None = Field(None, description="Описание закупки")
    organizer_id: uuid.UUID = Field(..., description="Идентификатор организатора")
    supplier_id: uuid.UUID | None = Field(None, description="Идентификатор утверждённого поставщика")
    category_id: uuid.UUID | None = Field(None, description="Идентификатор категории")
    city: str | None = Field(None, description="Город получения товара")
    status: str = Field(..., description="Статус закупки: draft | active | stopped | payment | completed | cancelled")
    target_amount: Decimal = Field(..., description="Целевая сумма закупки")
    current_amount: Decimal = Field(..., description="Текущая собранная сумма")
    stop_at_amount: Decimal | None = Field(None, description="Стоп-сумма")
    commission_pct: Decimal = Field(..., description="Комиссия организатора (%)")
    unit: str = Field(..., description="Единица измерения")
    price_per_unit: Decimal | None = Field(None, description="Цена за единицу")
    deadline: datetime | None = Field(None, description="Срок окончания")
    image_url: str | None = Field(None, description="Ссылка на изображение")
    is_featured: bool = Field(..., description="Рекомендованная закупка")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = {"from_attributes": True}


class PurchaseStatusUpdate(BaseModel):
    status: str = Field(..., description="Новый статус: draft | active | stopped | payment | completed | cancelled", example="active")

    model_config = {
        "json_schema_extra": {"example": {"status": "active"}}
    }


# ── Votes / Supplier selection ────────────────────────────────────────────────

class VoteCreate(BaseModel):
    value: int = Field(1, description="Вес голоса", example=1)
    candidate_id: uuid.UUID | None = Field(None, description="Идентификатор кандидата-поставщика")

    model_config = {
        "json_schema_extra": {"example": {"value": 1, "candidate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}}
    }


class VoteOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор голоса")
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки")
    user_id: uuid.UUID = Field(..., description="Идентификатор проголосовавшего пользователя")
    value: int = Field(..., description="Вес голоса")
    candidate_id: uuid.UUID | None = Field(None, description="Идентификатор кандидата")
    created_at: datetime = Field(..., description="Дата голосования")

    model_config = {"from_attributes": True}


class VoteResultOut(BaseModel):
    candidate_id: uuid.UUID | None = Field(None, description="Идентификатор кандидата-поставщика")
    total_votes: int = Field(..., description="Количество голосов")
    total_value: int = Field(..., description="Суммарный вес голосов")


class ApproveSupplierRequest(BaseModel):
    supplier_id: uuid.UUID = Field(..., description="Идентификатор утверждаемого поставщика")

    model_config = {
        "json_schema_extra": {"example": {"supplier_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}}
    }


# ── Participants ──────────────────────────────────────────────────────────────

class JoinPurchaseRequest(BaseModel):
    quantity: Decimal = Field(Decimal("1"), gt=0, description="Количество товара с учётом единицы измерения организатора", example="5")
    amount: Decimal = Field(..., gt=0, description="Сумма участия в закупке", example="500.00")
    city: str = Field(..., min_length=1, max_length=100, description="Город получения товара", example="Москва")
    notes: str | None = Field(None, description="Примечания к заявке")

    model_config = {
        "json_schema_extra": {
            "example": {
                "quantity": "5",
                "amount": "500.00",
                "city": "Москва",
                "notes": "Доставка до склада",
            }
        }
    }


class ParticipantOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор участника")
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки")
    user_id: uuid.UUID = Field(..., description="Идентификатор покупателя")
    status: str = Field(..., description="Статус участия: pending | confirmed | paid | delivered | cancelled")
    quantity: Decimal = Field(..., description="Количество товара")
    amount: Decimal = Field(..., description="Сумма участия")
    city: str | None = Field(None, description="Город получения товара")
    notes: str | None = Field(None, description="Примечания")
    is_active: bool = Field(..., description="Участник активен")
    created_at: datetime = Field(..., description="Дата присоединения")

    model_config = {"from_attributes": True}
