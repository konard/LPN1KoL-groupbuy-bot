from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import ChatMessageModel
from app.services.auth_service import current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageOut(BaseModel):
    id: int
    room: str
    user_id: Optional[int]
    username: Optional[str]
    msg_type: str
    text: str
    timestamp: datetime

    class Config:
        from_attributes = True


class SocketEvent(BaseModel):
    type: str
    room: str
    user_id: str
    text: str
    timestamp: str


def _msg_out(m: ChatMessageModel) -> dict:
    return {
        "id": m.id, "room": m.room, "user_id": m.user_id,
        "username": m.user.username if m.user else None,
        "msg_type": m.msg_type, "text": m.text, "timestamp": m.timestamp,
    }


@router.get("/{room}/messages", response_model=list[ChatMessageOut])
def get_room_messages(
    room: str,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(current_user),
):
    msgs = (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.room == room)
        .order_by(ChatMessageModel.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [_msg_out(m) for m in reversed(msgs)]


@router.post("/internal/socket-event", status_code=204, include_in_schema=False)
def receive_socket_event(event: SocketEvent, db: Session = Depends(get_db)):
    try:
        user_id_int = int(event.user_id) if event.user_id.isdigit() else None
    except (ValueError, AttributeError):
        user_id_int = None
    msg = ChatMessageModel(
        room=event.room,
        user_id=user_id_int,
        msg_type=event.type,
        text=event.text,
        timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
    )
    db.add(msg)
    db.commit()
