import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NewsCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Заголовок новости", example="Новая закупка открыта")
    content: str = Field(..., min_length=1, description="Текст новости", example="Объявляем о начале новой закупки на товар...")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Новая закупка открыта",
                "content": "Объявляем о начале новой групповой закупки на партию товаров.",
            }
        }
    }


class NewsUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255, description="Заголовок новости")
    content: str | None = Field(None, min_length=1, description="Текст новости")


class NewsOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор новости")
    author_id: uuid.UUID = Field(..., description="Идентификатор автора")
    title: str = Field(..., description="Заголовок новости")
    content: str = Field(..., description="Текст новости")
    is_published: bool = Field(..., description="Признак публикации")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "author_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "title": "Новая закупка открыта",
                "content": "Объявляем о начале новой групповой закупки.",
                "is_published": True,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
            }
        },
    }
