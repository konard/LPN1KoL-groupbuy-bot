"""
Pydantic-схемы для модуля чата.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    """Создание новой комнаты (чата)."""
    name: str
    # Тип: purchase | direct | group
    type: str = "group"
    purchase_id: Optional[int] = None
    member_ids: List[int] = []


class RoomOut(BaseModel):
    """Данные комнаты."""
    id: int
    name: str
    type: str
    purchase_id: Optional[int]
    created_by: int
    is_archived: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    """Отправка сообщения в комнату."""
    content: str
    # Тип: text | system | image | video | file
    type: str = "text"
    media_url: Optional[str] = None


class EditMessageRequest(BaseModel):
    """Редактирование сообщения."""
    content: str


class MessageOut(BaseModel):
    """Данные сообщения."""
    id: int
    room_id: int
    user_id: Optional[int]
    content: str
    type: str
    media_url: Optional[str]
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CentrifugoTokenOut(BaseModel):
    """JWT-токен для подключения к Centrifugo WebSocket."""
    token: str
