"""Chat and notification endpoints — mirrors core-rust handlers/chat.rs"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateMessage

logger = logging.getLogger("core.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages/", summary="List messages")
async def list_messages(
    procurement: int | None = Query(default=None),
    user: UUID | None = Query(default=None),
    pool=Depends(get_pool),
):
    if procurement is not None:
        rows = await pool.fetch(
            "SELECT * FROM chat_messages WHERE procurement_id=$1 AND is_deleted=false ORDER BY created_at ASC",
            procurement,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM chat_messages WHERE is_deleted=false ORDER BY created_at ASC LIMIT 100"
        )
    return {"results": [dict(r) for r in rows]}


@router.post("/messages/", status_code=201, summary="Create message")
async def create_message(body: CreateMessage, pool=Depends(get_pool)):
    try:
        row = await pool.fetchrow(
            """INSERT INTO chat_messages (procurement_id, user_id, message_type, text, attachment_url)
               VALUES ($1,$2,$3,$4,$5)
               RETURNING *""",
            body.procurement,
            body.user,
            body.message_type or "text",
            body.text,
            body.attachment_url or "",
        )
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/messages/unread_count/", summary="Count unread messages for a user in a procurement")
async def unread_count(
    user_id: UUID = Query(...),
    procurement_id: int = Query(...),
    pool=Depends(get_pool),
):
    last_read = await pool.fetchval(
        """SELECT last_read_message_id FROM message_reads
            WHERE user_id=$1 AND procurement_id=$2""",
        user_id, procurement_id,
    )
    if last_read is None:
        count = await pool.fetchval(
            """SELECT COUNT(*) FROM chat_messages
                WHERE procurement_id=$1 AND is_deleted=false AND user_id <> $2""",
            procurement_id, user_id,
        ) or 0
    else:
        count = await pool.fetchval(
            """SELECT COUNT(*) FROM chat_messages
                WHERE procurement_id=$1 AND is_deleted=false
                  AND id > $2 AND user_id <> $3""",
            procurement_id, int(last_read), user_id,
        ) or 0
    return {"unread_count": int(count)}


@router.post("/messages/mark_read/", summary="Mark messages as read")
async def mark_messages_read(body: dict, pool=Depends(get_pool)):
    user_id_str = body.get("user_id")
    procurement_id = body.get("procurement_id")
    if not user_id_str or procurement_id is None:
        raise HTTPException(status_code=400, detail="user_id and procurement_id are required")
    try:
        user_uuid = UUID(user_id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="user_id must be a valid UUID")

    message_id = body.get("message_id")
    if message_id is None:
        message_id = await pool.fetchval(
            "SELECT id FROM chat_messages WHERE procurement_id=$1 AND is_deleted=false ORDER BY created_at DESC LIMIT 1",
            int(procurement_id),
        )

    if message_id is not None:
        await pool.execute(
            """INSERT INTO message_reads (user_id, procurement_id, last_read_message_id)
               VALUES ($1,$2,$3)
               ON CONFLICT (user_id, procurement_id) DO UPDATE SET last_read_message_id=EXCLUDED.last_read_message_id""",
            user_uuid, int(procurement_id), int(message_id),
        )
    return {"message": "Marked as read"}


@router.get("/notifications/", summary="List notifications")
async def list_notifications(user_id: UUID | None = Query(default=None), pool=Depends(get_pool)):
    if user_id is not None:
        rows = await pool.fetch(
            "SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC", user_id
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100"
        )
    return [dict(r) for r in rows]


@router.post("/notifications/{notification_id}/mark_read/", summary="Mark notification as read")
async def mark_notification_read(notification_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        "UPDATE notifications SET is_read=true WHERE id=$1 RETURNING *", notification_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return dict(row)
