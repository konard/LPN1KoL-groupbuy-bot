"""
Роутер чата (/api/chat/*).
Перенесён из chat-service (порт 4004).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.clients.centrifugo_client import generate_centrifugo_token
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.chat import (
    CentrifugoTokenOut, CreateRoomRequest, EditMessageRequest,
    MessageOut, RoomOut, SendMessageRequest,
)
from app.services import chat_service as svc

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/rooms", response_model=RoomOut, status_code=201)
async def create_room(data: CreateRoomRequest, db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    """Создаёт новую комнату и добавляет участников."""
    return svc.create_room(db, data.name, data.type, user.id, data.purchase_id, data.member_ids)


@router.get("/rooms", response_model=List[RoomOut])
def list_rooms(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Возвращает все комнаты, в которых состоит пользователь."""
    return svc.list_user_rooms(db, user.id)


@router.post("/rooms/{room_id}/members/{member_id}", status_code=204)
async def add_member(room_id: int, member_id: int, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    """Добавляет пользователя в комнату."""
    svc.add_member(db, room_id, member_id)


@router.get("/rooms/{room_id}/messages", response_model=List[MessageOut])
def get_messages(
    room_id: int,
    before_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Возвращает сообщения комнаты (newest-first, курсорная пагинация)."""
    return svc.get_messages(db, room_id, before_id, limit)


@router.post("/rooms/{room_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(room_id: int, data: SendMessageRequest,
                       db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """Отправляет сообщение в комнату и публикует в Centrifugo-канал."""
    return await svc.send_message(db, room_id, user.id, data.content, data.type, data.media_url)


@router.put("/rooms/{room_id}/messages/{message_id}", response_model=MessageOut)
async def edit_message(room_id: int, message_id: int, data: EditMessageRequest,
                       db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """Редактирует сообщение. Только автор может редактировать."""
    return svc.edit_message(db, message_id, user.id, data.content)


@router.delete("/rooms/{room_id}/messages/{message_id}", status_code=204)
async def delete_message(room_id: int, message_id: int,
                         db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    """Мягко удаляет сообщение."""
    svc.delete_message(db, message_id, user.id)


@router.get("/centrifugo/token", response_model=CentrifugoTokenOut)
def get_centrifugo_token(user=Depends(get_current_user)):
    """Выдаёт JWT-токен для подключения к Centrifugo WebSocket."""
    token = generate_centrifugo_token(str(user.id))
    return CentrifugoTokenOut(token=token)
