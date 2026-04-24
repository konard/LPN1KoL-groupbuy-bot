import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.purchase import schemas, service

router = APIRouter(prefix="/purchases", tags=["Закупки"])
categories_router = APIRouter(prefix="/api/v1/categories", tags=["Категории"])


# ── Category endpoints ────────────────────────────────────────────────────────


@categories_router.get(
    "",
    response_model=list[schemas.CategoryOut],
    summary="Список категорий",
    description="Возвращает список категорий товаров. При передаче parent_id возвращает дочерние категории.",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_categories(
    parent_id: uuid.UUID | None = Query(None, description="Идентификатор родительской категории"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список категорий товаров."""
    return await service.list_categories(db, parent_id=parent_id)


@categories_router.post(
    "",
    response_model=schemas.CategoryOut,
    status_code=201,
    summary="Создать категорию",
    description="Создаёт новую категорию товаров.",
    responses={422: {"description": "Ошибка валидации данных"}},
)
async def create_category(
    req: schemas.CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Создать новую категорию товаров."""
    return await service.create_category(db, req)


@categories_router.get(
    "/{category_id}",
    response_model=schemas.CategoryOut,
    summary="Получить категорию",
    description="Возвращает данные категории по её идентификатору.",
    responses={404: {"description": "Категория не найдена"}},
)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить категорию по идентификатору."""
    cat = await service.get_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return cat


# ── Purchase / Procurement endpoints ─────────────────────────────────────────


@router.post(
    "",
    response_model=schemas.PurchaseOut,
    status_code=201,
    summary="Создать закупку",
    description=(
        "Позволяет организатору создать новую групповую закупку. "
        "После создания закупка добавляется в горизонтальный слайдер и отображается в общем чате. "
        "Поля: название товара, единица измерения, город получения, описание, "
        "комиссия организатора (1–4%), минимальное количество товара (необязательно)."
    ),
    responses={
        403: {"description": "Только организаторы могут создавать закупки"},
        422: {"description": "Ошибка валидации данных (комиссия должна быть от 1% до 4%)"},
    },
)
async def create_purchase(
    req: schemas.PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новую групповую закупку (только организатор)."""
    return await service.create_purchase(db, req, current_user.id)


@router.get(
    "",
    response_model=list[schemas.PurchaseOut],
    summary="Список закупок",
    description=(
        "Возвращает список закупок с возможностью фильтрации по статусу, городу, категории, "
        "организатору. Поддерживает пагинацию (skip/limit)."
    ),
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_purchases(
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    status: str | None = Query(None, description="Фильтр по статусу: draft | active | stopped | payment | completed | cancelled"),
    city: str | None = Query(None, description="Фильтр по городу"),
    category_id: uuid.UUID | None = Query(None, description="Фильтр по категории"),
    organizer_id: uuid.UUID | None = Query(None, description="Фильтр по организатору"),
    active_only: bool = Query(False, description="Только активные закупки"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список закупок с фильтрами."""
    return await service.list_purchases(
        db,
        skip=skip,
        limit=limit,
        status=status,
        city=city,
        category_id=category_id,
        organizer_id=organizer_id,
        active_only=active_only,
    )


@router.get(
    "/user/{user_id}",
    response_model=list[schemas.PurchaseOut],
    summary="Закупки пользователя",
    description="Возвращает список закупок, организованных указанным пользователем.",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_user_purchases(
    user_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить закупки конкретного организатора."""
    return await service.list_purchases(db, skip=skip, limit=limit, organizer_id=user_id)


@router.get(
    "/{purchase_id}",
    response_model=schemas.PurchaseOut,
    summary="Получить закупку",
    description="Возвращает детали конкретной закупки по её идентификатору.",
    responses={404: {"description": "Закупка не найдена"}},
)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить закупку по идентификатору."""
    p = await service.get_purchase(db, purchase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Закупка не найдена")
    return p


@router.post(
    "/{purchase_id}/update_status",
    response_model=schemas.PurchaseOut,
    summary="Обновить статус закупки",
    description=(
        "Изменяет статус закупки. Доступно только организатору. "
        "Допустимые статусы: draft, active, stopped, payment, completed, cancelled."
    ),
    responses={
        400: {"description": "Недопустимый статус"},
        403: {"description": "Только организатор может менять статус закупки"},
        404: {"description": "Закупка не найдена"},
    },
)
async def update_status(
    purchase_id: uuid.UUID,
    req: schemas.PurchaseStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить статус закупки (только организатор)."""
    return await service.update_status(db, purchase_id, req.status, current_user.id)


@router.post(
    "/{purchase_id}/close",
    response_model=schemas.PurchaseOut,
    summary="Закрыть закупку",
    description=(
        "Завершает закупку — переводит её в статус 'completed'. "
        "После нажатия закупка перемещается в историю. Доступно только организатору."
    ),
    responses={
        403: {"description": "Только организатор может закрыть закупку"},
        404: {"description": "Закупка не найдена"},
    },
)
async def close_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Закрыть закупку (только организатор)."""
    return await service.close_purchase(db, purchase_id, current_user.id)


@router.post(
    "/{purchase_id}/approve_supplier",
    response_model=schemas.PurchaseOut,
    summary="Утвердить поставщика",
    description=(
        "Утверждает выбранного поставщика для закупки и переводит её в стадию оплаты. "
        "После утверждения поставщик добавляется в информацию о закупке. Доступно только организатору."
    ),
    responses={
        403: {"description": "Только организатор может утверждать поставщика"},
        404: {"description": "Закупка не найдена"},
    },
)
async def approve_supplier(
    purchase_id: uuid.UUID,
    req: schemas.ApproveSupplierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Утвердить поставщика (только организатор)."""
    return await service.approve_supplier(db, purchase_id, req.supplier_id, current_user.id)


@router.post(
    "/{purchase_id}/stop_amount",
    response_model=schemas.PurchaseOut,
    summary="Стоп-сумма",
    description=(
        "Останавливает закупку (стоп-сумма) и создаёт закрытый чат для участников. "
        "После нажатия участники получают уведомление с просьбой подтвердить участие. "
        "Участники, подтвердившие участие, переносятся в закрытый чат. Доступно только организатору."
    ),
    responses={
        403: {"description": "Только организатор может применить стоп-сумму"},
        404: {"description": "Закупка не найдена"},
    },
)
async def stop_amount(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Применить стоп-сумму (только организатор)."""
    return await service.stop_amount(db, purchase_id, current_user.id)


@router.get(
    "/{purchase_id}/receipt_table",
    summary="Таблица чеков",
    description=(
        "Формирует сводную таблицу чеков участников закупки для отправки поставщику. "
        "Содержит данные о платежах: пользователь, количество, сумма, статус."
    ),
    responses={404: {"description": "Закупка не найдена"}},
)
async def receipt_table(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить сводную таблицу чеков для поставщика."""
    return await service.get_receipt_table(db, purchase_id)


# ── Participant endpoints ─────────────────────────────────────────────────────


@router.get(
    "/{purchase_id}/participants",
    response_model=list[schemas.ParticipantOut],
    summary="Участники закупки",
    description="Возвращает список активных участников закупки.",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_participants(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список участников закупки."""
    return await service.list_participants(db, purchase_id)


@router.post(
    "/{purchase_id}/join",
    response_model=schemas.ParticipantOut,
    status_code=201,
    summary="Присоединиться к закупке",
    description=(
        "Позволяет покупателю добавиться в закупку. "
        "Поля: количество товара (с учётом единиц измерения организатора), "
        "сумма участия, город получения товара. "
        "Покупатель может редактировать данные до подтверждения закупки организатором."
    ),
    responses={
        400: {"description": "Нельзя присоединиться к закупке (неверный статус или уже участвует)"},
        404: {"description": "Закупка не найдена"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def join_purchase(
    purchase_id: uuid.UUID,
    req: schemas.JoinPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Присоединиться к закупке как участник."""
    return await service.join_purchase(db, purchase_id, current_user.id, req)


@router.post(
    "/{purchase_id}/leave",
    summary="Выйти из закупки",
    description="Позволяет покупателю выйти из закупки. Кнопка «Удалить из заявки».",
    responses={
        404: {"description": "Закупка или участие не найдены"},
    },
)
async def leave_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Выйти из закупки."""
    return await service.leave_purchase(db, purchase_id, current_user.id)


# ── Vote endpoints ────────────────────────────────────────────────────────────


@router.post(
    "/{purchase_id}/vote",
    response_model=schemas.VoteOut,
    status_code=201,
    summary="Проголосовать за поставщика",
    description=(
        "Покупатели голосуют за одного из предложенных поставщиков. "
        "Система подсчитывает голоса и определяет победителя."
    ),
    responses={
        404: {"description": "Закупка не найдена"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def vote(
    purchase_id: uuid.UUID,
    req: schemas.VoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проголосовать за поставщика в закупке."""
    return await service.cast_vote(db, purchase_id, current_user.id, req)


@router.get(
    "/{purchase_id}/vote_results",
    response_model=list[schemas.VoteResultOut],
    summary="Результаты голосования",
    description="Возвращает агрегированные результаты голосования за поставщиков по закупке.",
    responses={404: {"description": "Закупка не найдена"}},
)
async def vote_results(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить результаты голосования за поставщиков."""
    return await service.get_vote_results(db, purchase_id)
