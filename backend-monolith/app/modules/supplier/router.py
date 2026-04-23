import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.supplier import schemas, service

router = APIRouter(prefix="/api/v1/supplier", tags=["Поставщик"])


def require_supplier(current_user: User) -> User:
    if current_user.role != "supplier":
        raise HTTPException(
            status_code=403,
            detail="Только поставщики могут выполнять это действие",
        )
    return current_user


# ── Карта компании ────────────────────────────────────────────────────────────


@router.post(
    "/company-card",
    response_model=schemas.CompanyCardOut,
    status_code=201,
    summary="Создать карту компании",
    description=(
        "Позволяет поставщику создать карту компании. "
        "Поля: название компании, юридический адрес, почтовый адрес, фактический адрес, "
        "ОКВЭД, ОГРН, ИНН, контактный телефон, электронная почта. "
        "Все поля обязательны. После создания карта публикуется в публичной части кабинета."
    ),
    responses={
        400: {"description": "Карта компании уже существует"},
        403: {"description": "Только поставщики могут создавать карту компании"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def create_company_card(
    req: schemas.CompanyCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать карту компании (только поставщик)."""
    require_supplier(current_user)
    return await service.get_or_create_company_card(db, current_user.id, req)


@router.get(
    "/company-card",
    response_model=schemas.CompanyCardOut,
    summary="Получить карту компании",
    description="Возвращает карту компании текущего поставщика.",
    responses={
        403: {"description": "Только поставщики могут просматривать свою карту"},
        404: {"description": "Карта компании не найдена"},
    },
)
async def get_my_company_card(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить карту компании текущего поставщика."""
    require_supplier(current_user)
    card = await service.get_company_card(db, current_user.id)
    if not card:
        raise HTTPException(status_code=404, detail="Карта компании не найдена")
    return card


@router.get(
    "/{supplier_id}/company-card",
    response_model=schemas.CompanyCardOut,
    summary="Получить карту компании поставщика",
    description="Возвращает публичную карту компании поставщика по его идентификатору.",
    responses={404: {"description": "Карта компании не найдена"}},
)
async def get_supplier_company_card(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить публичную карту компании поставщика."""
    card = await service.get_company_card(db, supplier_id)
    if not card:
        raise HTTPException(status_code=404, detail="Карта компании не найдена")
    return card


@router.patch(
    "/company-card",
    response_model=schemas.CompanyCardOut,
    summary="Обновить карту компании",
    description="Позволяет поставщику обновить данные карты компании.",
    responses={
        403: {"description": "Только поставщики могут редактировать карту компании"},
        404: {"description": "Карта компании не найдена"},
        422: {"description": "Ошибка валидации"},
    },
)
async def update_company_card(
    req: schemas.CompanyCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить карту компании (только поставщик)."""
    require_supplier(current_user)
    return await service.update_company_card(db, current_user.id, req)


# ── Прайс-лист ────────────────────────────────────────────────────────────────


@router.post(
    "/price-list",
    response_model=schemas.PriceListOut,
    status_code=201,
    summary="Загрузить прайс-лист",
    description=(
        "Позволяет поставщику загрузить прайс-лист (файл). "
        "Предыдущий активный прайс-лист деактивируется. "
        "Дополнительно можно указать список до 20 самых популярных товаров с ценами."
    ),
    responses={
        403: {"description": "Только поставщики могут загружать прайс-листы"},
        422: {"description": "Ошибка валидации"},
    },
)
async def upload_price_list(
    file: UploadFile = File(..., description="Файл прайс-листа"),
    popular_items: str | None = Form(None, description="Список популярных товаров (до 20 позиций)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузить прайс-лист (только поставщик)."""
    require_supplier(current_user)
    return await service.create_price_list(db, current_user.id, file, popular_items)


@router.get(
    "/price-list",
    response_model=schemas.PriceListOut | None,
    summary="Получить прайс-лист",
    description="Возвращает активный прайс-лист текущего поставщика.",
    responses={403: {"description": "Только поставщики могут просматривать свой прайс-лист"}},
)
async def get_my_price_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить активный прайс-лист текущего поставщика."""
    require_supplier(current_user)
    return await service.get_active_price_list(db, current_user.id)


@router.get(
    "/{supplier_id}/price-list",
    response_model=schemas.PriceListOut | None,
    summary="Получить прайс-лист поставщика",
    description="Возвращает активный прайс-лист поставщика по его идентификатору.",
    responses={404: {"description": "Прайс-лист не найден"}},
)
async def get_supplier_price_list(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить активный прайс-лист поставщика."""
    return await service.get_active_price_list(db, supplier_id)


# ── Закрывающие документы ─────────────────────────────────────────────────────


@router.post(
    "/closing-documents",
    response_model=schemas.ClosingDocumentOut,
    status_code=201,
    summary="Отправить закрывающие документы",
    description=(
        "Позволяет поставщику загрузить и отправить закрывающие документы покупателям по закупке. "
        "После загрузки документы становятся доступны участникам закупки."
    ),
    responses={
        403: {"description": "Только поставщики могут отправлять закрывающие документы"},
        422: {"description": "Ошибка валидации"},
    },
)
async def upload_closing_document(
    purchase_id: uuid.UUID = Form(..., description="Идентификатор закупки"),
    file: UploadFile = File(..., description="Файл закрывающего документа"),
    comment: str | None = Form(None, description="Комментарий для покупателей"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправить закрывающие документы (только поставщик)."""
    require_supplier(current_user)
    return await service.create_closing_document(
        db, current_user.id, purchase_id, file, comment
    )


@router.get(
    "/closing-documents",
    response_model=list[schemas.ClosingDocumentOut],
    summary="Список закрывающих документов",
    description="Возвращает список закрывающих документов по закупке.",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_closing_documents(
    purchase_id: uuid.UUID = Query(..., description="Идентификатор закупки"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить закрывающие документы по закупке."""
    return await service.list_closing_documents(db, purchase_id)
