import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.requests import schemas, service

router = APIRouter(prefix="/api/v1/requests", tags=["Запросы покупателей"])


@router.post(
    "",
    response_model=schemas.BuyerRequestOut,
    status_code=201,
    summary="Создать запрос на товар",
    description=(
        "Позволяет покупателю создать новый запрос на товар. "
        "После заполнения формы запрос добавляется в общий чат и отображается в вертикальной ленте. "
        "Поля: название товара, количество, город получения, примечание (необязательно)."
    ),
    responses={
        403: {"description": "Только покупатели могут создавать запросы на товар"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def create_request(
    req: schemas.BuyerRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать запрос на товар (только покупатель)."""
    if current_user.role != "buyer":
        raise HTTPException(
            status_code=403,
            detail="Только покупатели могут создавать запросы на товар",
        )
    return await service.create_request(db, req, current_user.id)


@router.get(
    "",
    response_model=list[schemas.BuyerRequestOut],
    summary="Список запросов на товары",
    description=(
        "Возвращает список активных запросов на товары. "
        "При передаче параметра buyer_id возвращает только запросы указанного покупателя."
    ),
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_requests(
    buyer_id: uuid.UUID | None = Query(None, description="Фильтр по покупателю"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список запросов на товары."""
    return await service.list_requests(db, buyer_id=buyer_id, skip=skip, limit=limit)


@router.get(
    "/my",
    response_model=list[schemas.BuyerRequestOut],
    summary="Мои запросы",
    description="Возвращает список запросов на товары, созданных текущим покупателем.",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def my_requests(
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить мои запросы на товары."""
    return await service.list_requests(db, buyer_id=current_user.id, skip=skip, limit=limit)


@router.get(
    "/{request_id}",
    response_model=schemas.BuyerRequestOut,
    summary="Получить запрос",
    description="Возвращает детали конкретного запроса на товар по его идентификатору.",
    responses={
        404: {"description": "Запрос не найден"},
        422: {"description": "Ошибка валидации"},
    },
)
async def get_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить запрос по идентификатору."""
    buyer_request = await service.get_request(db, request_id)
    if not buyer_request or not buyer_request.is_active:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    return buyer_request


@router.patch(
    "/{request_id}",
    response_model=schemas.BuyerRequestOut,
    summary="Редактировать запрос",
    description="Позволяет покупателю отредактировать свой запрос на товар до его исполнения.",
    responses={
        403: {"description": "Нет прав для редактирования"},
        404: {"description": "Запрос не найден"},
        422: {"description": "Ошибка валидации"},
    },
)
async def update_request(
    request_id: uuid.UUID,
    req: schemas.BuyerRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Редактировать запрос на товар (только автор)."""
    return await service.update_request(db, request_id, req, current_user.id)


@router.delete(
    "/{request_id}",
    summary="Удалить запрос",
    description="Удаляет (деактивирует) запрос на товар. Доступно только автору запроса.",
    responses={
        403: {"description": "Нет прав для удаления"},
        404: {"description": "Запрос не найден"},
    },
)
async def delete_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить запрос на товар (только автор)."""
    return await service.delete_request(db, request_id, current_user.id)
