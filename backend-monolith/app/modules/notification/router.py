from fastapi import APIRouter, BackgroundTasks, Depends

from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.notification import service
from app.modules.notification.schemas import NotifyRequest

router = APIRouter(prefix="/api/v1/notify", tags=["notification"])


@router.post("")
async def notify(
    req: NotifyRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
):
    background_tasks.add_task(service.dispatch, req.user_id, req.type, req.payload)
    return {"queued": True}
