import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RoomCreate(BaseModel):
    name: str | None = Field(None, description="Название комнаты чата")
    type: str = Field("group", description="Тип комнаты: direct (личный), group (групповой), purchase (чат закупки)", example="group")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор закупки (для типа purchase)")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"direct", "group", "purchase"}
        if v not in allowed:
            raise ValueError(f"Тип должен быть одним из: {allowed}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {"name": "Закупка муки", "type": "purchase", "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        }
    }


class RoomOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор комнаты")
    name: str | None = Field(None, description="Название комнаты")
    type: str = Field(..., description="Тип комнаты: direct | group | purchase")
    purchase_id: uuid.UUID | None = Field(None, description="Идентификатор связанной закупки")
    created_by: uuid.UUID = Field(..., description="Идентификатор создателя")
    is_archived: bool = Field(..., description="Комната архивирована")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Содержимое сообщения", example="Добрый день, когда планируется отгрузка?")
    type: str = Field("text", description="Тип сообщения: text (текст), system (системное), image (изображение), file (файл)", example="text")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"text", "system", "image", "file"}
        if v not in allowed:
            raise ValueError(f"Тип должен быть одним из: {allowed}")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Сообщение не может быть пустым")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {"content": "Добрый день, когда планируется отгрузка?", "type": "text"}
        }
    }


class MessageOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор сообщения")
    room_id: uuid.UUID = Field(..., description="Идентификатор комнаты")
    user_id: uuid.UUID = Field(..., description="Идентификатор отправителя")
    content: str = Field(..., description="Содержимое сообщения")
    type: str = Field(..., description="Тип сообщения")
    media_url: str | None = Field(None, description="Ссылка на медиафайл")
    is_edited: bool = Field(..., description="Сообщение было отредактировано")
    is_deleted: bool = Field(..., description="Сообщение удалено")
    created_at: datetime = Field(..., description="Дата отправки")

    model_config = {"from_attributes": True}
