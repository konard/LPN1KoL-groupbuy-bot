"""
Socket.IO server replacing Centrifugo for real-time chat.

Authentication: clients pass the JWT in the `auth` handshake dict:
    socket = io(url, { auth: { token: "<jwt>" } })

Room naming: "room:<room_uuid>"

Production note: set REDIS_URL env var to enable AsyncRedisManager so that
multiple monolith replicas share pub/sub state.
"""
import logging

import socketio
from jose import JWTError

from app.config import settings
from app.modules.auth.service import decode_token

logger = logging.getLogger(__name__)

# NOTE: Use AsyncRedisManager when REDIS_URL is set so that horizontal scaling
# works out of the box without changing application code.
if settings.redis_url:
    mgr = socketio.AsyncRedisManager(settings.redis_url)
    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=mgr,
        cors_allowed_origins=settings.cors_origins if settings.cors_origins != "*" else "*",
    )
else:
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=settings.cors_origins if settings.cors_origins != "*" else "*",
    )


def _authenticate(auth: dict | None) -> dict | None:
    if not auth:
        return None
    token = auth.get("token")
    if not token:
        return None
    try:
        return decode_token(token)
    except JWTError:
        return None


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None):
    payload = _authenticate(auth)
    if payload is None:
        logger.warning("Socket.IO connection rejected — invalid JWT (sid=%s)", sid)
        raise ConnectionRefusedError("authentication required")
    user_id = payload.get("sub", "unknown")
    await sio.save_session(sid, {"user_id": user_id, "email": payload.get("email", "")})
    logger.info("Socket.IO connected: user=%s sid=%s", user_id, sid)


@sio.event
async def disconnect(sid: str):
    session = await sio.get_session(sid)
    logger.info("Socket.IO disconnected: user=%s sid=%s", session.get("user_id"), sid)


@sio.event
async def join_room(sid: str, data: dict):
    room_id = data.get("room_id")
    if not room_id:
        return {"error": True, "code": "MISSING_ROOM_ID", "message": "room_id required"}
    session = await sio.get_session(sid)
    await sio.enter_room(sid, f"room:{room_id}")
    logger.info("user=%s joined room=%s", session.get("user_id"), room_id)
    return {"joined": room_id}


@sio.event
async def leave_room(sid: str, data: dict):
    room_id = data.get("room_id")
    if not room_id:
        return {"error": True, "code": "MISSING_ROOM_ID", "message": "room_id required"}
    await sio.leave_room(sid, f"room:{room_id}")
    return {"left": room_id}


@sio.event
async def message(sid: str, data: dict):
    room_id = data.get("room_id")
    content = data.get("content", "").strip()
    if not room_id or not content:
        return {"error": True, "code": "INVALID_PAYLOAD", "message": "room_id and content required"}
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    event = {
        "room_id": room_id,
        "user_id": user_id,
        "content": content,
        "type": data.get("type", "text"),
    }
    await sio.emit("message", event, room=f"room:{room_id}", skip_sid=sid)
    return {"sent": True}


@sio.event
async def typing(sid: str, data: dict):
    room_id = data.get("room_id")
    if not room_id:
        return
    session = await sio.get_session(sid)
    await sio.emit(
        "typing",
        {"room_id": room_id, "user_id": session.get("user_id")},
        room=f"room:{room_id}",
        skip_sid=sid,
    )
