"""
Бизнес-логика чата: создание комнат, отправка и редактирование сообщений.
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.clients.centrifugo_client import publish_to_channel
from app.models.chat import MessageModel, RoomMemberModel, RoomModel

logger = logging.getLogger(__name__)


def create_room(db: Session, name: str, room_type: str, created_by: int,
                purchase_id: int | None, member_ids: list[int]) -> RoomModel:
    """Создаёт комнату и добавляет указанных участников."""
    room = RoomModel(
        name=name,
        type=room_type,
        created_by=created_by,
        purchase_id=purchase_id,
    )
    db.add(room)
    db.flush()

    # Добавляем создателя и переданных участников
    all_members = list(set([created_by] + member_ids))
    for uid in all_members:
        db.add(RoomMemberModel(room_id=room.id, user_id=uid))

    db.commit()
    db.refresh(room)
    return room


def list_user_rooms(db: Session, user_id: int) -> list[RoomModel]:
    """Возвращает все комнаты, в которых состоит пользователь."""
    room_ids = (
        db.query(RoomMemberModel.room_id)
        .filter(RoomMemberModel.user_id == user_id)
        .subquery()
    )
    return db.query(RoomModel).filter(RoomModel.id.in_(room_ids)).all()


def add_member(db: Session, room_id: int, user_id: int) -> None:
    """Добавляет пользователя в комнату."""
    existing = db.query(RoomMemberModel).filter(
        RoomMemberModel.room_id == room_id,
        RoomMemberModel.user_id == user_id,
    ).first()
    if not existing:
        db.add(RoomMemberModel(room_id=room_id, user_id=user_id))
        db.commit()


def get_messages(db: Session, room_id: int, before_id: int | None = None,
                 limit: int = 50) -> list[MessageModel]:
    """Возвращает сообщения комнаты с курсорной пагинацией."""
    q = db.query(MessageModel).filter(
        MessageModel.room_id == room_id,
        MessageModel.is_deleted == False,  # noqa: E712
    )
    if before_id:
        q = q.filter(MessageModel.id < before_id)
    return q.order_by(MessageModel.created_at.desc()).limit(limit).all()


async def send_message(db: Session, room_id: int, user_id: int, content: str,
                       msg_type: str = "text", media_url: str | None = None) -> MessageModel:
    """Сохраняет сообщение и публикует его в Centrifugo-канал."""
    msg = MessageModel(
        room_id=room_id,
        user_id=user_id,
        content=content,
        type=msg_type,
        media_url=media_url,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Уведомляем подключённых клиентов через Centrifugo
    await publish_to_channel(
        f"room:{room_id}",
        {
            "id": msg.id,
            "user_id": user_id,
            "content": content,
            "type": msg_type,
            "created_at": msg.created_at.isoformat(),
        },
    )
    return msg


def edit_message(db: Session, message_id: int, user_id: int, new_content: str) -> MessageModel:
    """Редактирует сообщение. Только автор может редактировать."""
    msg = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")
    if msg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на редактирование")
    msg.content = new_content
    msg.is_edited = True
    db.commit()
    db.refresh(msg)
    return msg


def delete_message(db: Session, message_id: int, user_id: int) -> None:
    """Мягкое удаление сообщения (is_deleted=True). Только автор может удалить."""
    msg = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")
    if msg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на удаление")
    msg.is_deleted = True
    db.commit()
