import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    target_id: uuid.UUID = Field(..., description="Идентификатор пользователя, которому оставляется отзыв")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор закупки (необязательно)")
    rating: int = Field(..., ge=1, le=5, description="Оценка от 1 до 5", example=5)
    comment: str | None = Field(None, description="Комментарий к отзыву", example="Отличный организатор, всё прошло гладко")

    model_config = {
        "json_schema_extra": {
            "example": {
                "target_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "rating": 5,
                "comment": "Отличный организатор, всё прошло гладко",
            }
        }
    }


class ReviewOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор отзыва")
    reviewer_id: uuid.UUID = Field(..., description="Идентификатор автора отзыва")
    target_id: uuid.UUID = Field(..., description="Идентификатор получателя отзыва")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор закупки")
    rating: int = Field(..., description="Оценка от 1 до 5")
    comment: str | None = Field(None, description="Комментарий")
    status: str = Field(..., description="Статус отзыва")
    created_at: datetime = Field(..., description="Дата создания отзыва")

    model_config = {"from_attributes": True}
