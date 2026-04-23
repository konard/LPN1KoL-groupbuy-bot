from fastapi import APIRouter, BackgroundTasks, Depends

from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.notification import service
from app.modules.notification.schemas import NotifyRequest

router = APIRouter(prefix="/api/v1/notify", tags=["Уведомления"])


@router.post(
    "",
    summary="Отправить уведомление",
    description=(
        "Ставит в очередь отправку уведомления пользователю. "
        "Поддерживаемые каналы: email, push (Firebase), telegram, websocket. "
        "Уведомление обрабатывается асинхронно."
    ),
    responses={422: {"description": "Ошибка валидации данных"}},
)
async def notify(
    req: NotifyRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
):
    """Отправить уведомление пользователю."""
    background_tasks.add_task(service.dispatch, req.user_id, req.type, req.payload)
    return {"queued": True}
