from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.invitations import schemas, service

router = APIRouter(prefix="/api/v1/invitations", tags=["Приглашения"])


@router.post(
    "/supplier",
    response_model=schemas.InvitationOut,
    status_code=201,
    summary="Пригласить поставщика",
    description=(
        "Позволяет организатору отправить приглашение поставщику по электронной почте. "
        "Поля: email поставщика, текст приглашения, идентификатор закупки (необязательно)."
    ),
    responses={
        403: {"description": "Только организаторы могут приглашать поставщиков"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def invite_supplier(
    req: schemas.InviteSupplierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пригласить поставщика (только организатор)."""
    if current_user.role != "organizer":
        raise HTTPException(
            status_code=403,
            detail="Только организаторы могут приглашать поставщиков",
        )
    return await service.invite_supplier(db, req, current_user.id)


@router.post(
    "/buyer",
    response_model=schemas.InvitationOut,
    status_code=201,
    summary="Пригласить покупателя",
    description=(
        "Позволяет организатору отправить приглашение покупателю присоединиться к закупке. "
        "Поля: текст приглашения, ссылка на закупку (purchase_id)."
    ),
    responses={
        403: {"description": "Только организаторы могут приглашать покупателей"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def invite_buyer(
    req: schemas.InviteBuyerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пригласить покупателя (только организатор)."""
    if current_user.role != "organizer":
        raise HTTPException(
            status_code=403,
            detail="Только организаторы могут приглашать покупателей",
        )
    return await service.invite_buyer(db, req, current_user.id)


@router.get(
    "/my",
    response_model=list[schemas.InvitationOut],
    summary="Мои приглашения",
    description="Возвращает список приглашений, полученных текущим пользователем.",
)
async def my_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список полученных приглашений."""
    return await service.list_my_invitations(db, current_user.id)


@router.get(
    "/sent",
    response_model=list[schemas.InvitationOut],
    summary="Отправленные приглашения",
    description="Возвращает список приглашений, отправленных текущим пользователем.",
)
async def sent_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список отправленных приглашений."""
    return await service.list_sent_invitations(db, current_user.id)
