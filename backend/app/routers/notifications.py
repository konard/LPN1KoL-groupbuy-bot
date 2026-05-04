"""
Роутер уведомлений (/api/notifications/*).
Перенесён из notification-service (порт 4005).
"""
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.notification import NotifyRequest
from app.services.notification_service import notify

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.post("/internal/notify", status_code=204)
async def internal_notify(data: NotifyRequest):
    """
    Внутренний endpoint для отправки уведомлений другими модулями.
    Без авторизации (только внутренняя сеть).
    """
    await notify(data.user_id, data.type, data.subject, data.message, data.extra)
