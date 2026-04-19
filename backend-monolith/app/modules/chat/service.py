import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import ChatMessage, Room
from app.modules.chat.schemas import MessageCreate, RoomCreate


async def create_room(db: AsyncSession, req: RoomCreate, user_id: uuid.UUID) -> Room:
    room = Room(
        name=req.name,
        type=req.type,
        purchase_id=req.purchase_id,
        created_by=user_id,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def list_rooms(db: AsyncSession) -> list[Room]:
    result = await db.scalars(select(Room).where(Room.is_archived.is_(False)))
    return list(result.all())


async def get_room(db: AsyncSession, room_id: uuid.UUID) -> Room | None:
    return await db.get(Room, room_id)


async def create_message(
    db: AsyncSession, room_id: uuid.UUID, req: MessageCreate, user_id: uuid.UUID
) -> ChatMessage:
    msg = ChatMessage(
        room_id=room_id,
        user_id=user_id,
        content=req.content,
        type=req.type,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession, room_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[ChatMessage]:
    result = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_id, ChatMessage.is_deleted.is_(False))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())
