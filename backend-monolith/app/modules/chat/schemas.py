import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class RoomCreate(BaseModel):
    name: str
    type: str = "group"
    purchase_id: uuid.UUID | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"direct", "group", "purchase"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class RoomOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    purchase_id: uuid.UUID | None
    created_by: uuid.UUID
    is_archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str
    type: str = "text"

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"text", "system", "image", "file"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class MessageOut(BaseModel):
    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    type: str
    media_url: str | None
    is_edited: bool
    is_deleted: bool
    created_at: datetime

    model_config = {"from_attributes": True}
