import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.kafka.producer import emit_event
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.chat import schemas, service

router = APIRouter(prefix="/api/v1/chat", tags=["Чат"])


@router.post(
    "/rooms",
    response_model=schemas.RoomOut,
    status_code=201,
    summary="Создать комнату чата",
    description=(
        "Создаёт новую комнату чата. "
        "Тип комнаты: direct (личный), group (групповой), purchase (чат закупки). "
        "Для закрытого чата участников закупки используется тип purchase с purchase_id."
    ),
    responses={422: {"description": "Ошибка валидации данных"}},
)
async def create_room(
    req: schemas.RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новую комнату чата."""
    room = await service.create_room(db, req, current_user.id)
    return room


@router.get(
    "/rooms",
    response_model=list[schemas.RoomOut],
    summary="Список комнат чата",
    description="Возвращает список активных комнат чата.",
)
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список комнат чата."""
    return await service.list_rooms(db)


@router.post(
    "/rooms/{room_id}/messages",
    response_model=schemas.MessageOut,
    status_code=201,
    summary="Отправить сообщение",
    description=(
        "Отправляет сообщение в чат-комнату. "
        "Пользователь вводит текст сообщения и нажимает «Отправить». "
        "Тип сообщения: text, system, image, file."
    ),
    responses={
        404: {"description": "Комната чата не найдена"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def send_message(
    room_id: uuid.UUID,
    req: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить сообщение в комнату чата."""
    room = await service.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комната чата не найдена")

    msg = await service.create_message(db, room_id, req, current_user.id)
    await emit_event(
        "chat.message.sent",
        str(current_user.id),
        {"room_id": str(room_id), "message_id": str(msg.id), "type": req.type},
    )
    return msg


@router.get(
    "/rooms/{room_id}/messages",
    response_model=list[schemas.MessageOut],
    summary="Получить сообщения",
    description="Возвращает список сообщений из комнаты чата с пагинацией.",
    responses={
        404: {"description": "Комната чата не найдена"},
        422: {"description": "Ошибка валидации параметров"},
    },
)
async def get_messages(
    room_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить историю сообщений чата."""
    room = await service.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комната чата не найдена")
    return await service.list_messages(db, room_id, limit=limit, offset=offset)
