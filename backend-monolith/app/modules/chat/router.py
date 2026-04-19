import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.kafka.producer import emit_event
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.chat import schemas, service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/rooms", response_model=schemas.RoomOut, status_code=201)
async def create_room(
    req: schemas.RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await service.create_room(db, req, current_user.id)
    return room


@router.get("/rooms", response_model=list[schemas.RoomOut])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await service.list_rooms(db)


@router.post("/rooms/{room_id}/messages", response_model=schemas.MessageOut, status_code=201)
async def send_message(
    room_id: uuid.UUID,
    req: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await service.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    msg = await service.create_message(db, room_id, req, current_user.id)
    await emit_event(
        "chat.message.sent",
        str(current_user.id),
        {"room_id": str(room_id), "message_id": str(msg.id), "type": req.type},
    )
    return msg


@router.get("/rooms/{room_id}/messages", response_model=list[schemas.MessageOut])
async def get_messages(
    room_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    room = await service.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return await service.list_messages(db, room_id, limit=limit, offset=offset)
