import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.news import schemas, service

router = APIRouter(prefix="/api/v1/news", tags=["Новости"])


@router.post(
    "",
    response_model=schemas.NewsOut,
    status_code=201,
    summary="Создать новость",
    description=(
        "Позволяет организатору или поставщику опубликовать новость в ленте новостей. "
        "После заполнения формы новость публикуется и становится доступна всем пользователям."
    ),
    responses={
        403: {"description": "Только организаторы и поставщики могут публиковать новости"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def create_news(
    req: schemas.NewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новость в ленте новостей (только организатор или поставщик)."""
    if current_user.role not in ("organizer", "supplier"):
        raise HTTPException(
            status_code=403,
            detail="Только организаторы и поставщики могут публиковать новости",
        )
    return await service.create_news(db, req, current_user.id)


@router.get(
    "",
    response_model=list[schemas.NewsOut],
    summary="Список новостей",
    description="Возвращает список опубликованных новостей от организаторов и поставщиков, отсортированных по дате публикации (новые первыми).",
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def list_news(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить список новостей."""
    return await service.list_news(db, skip=skip, limit=limit)


@router.get(
    "/{news_id}",
    response_model=schemas.NewsOut,
    summary="Получить новость",
    description="Возвращает детали конкретной новости по её идентификатору.",
    responses={
        404: {"description": "Новость не найдена"},
        422: {"description": "Ошибка валидации"},
    },
)
async def get_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Получить новость по идентификатору."""
    news = await service.get_news(db, news_id)
    if not news or not news.is_published:
        raise HTTPException(status_code=404, detail="Новость не найдена")
    return news


@router.patch(
    "/{news_id}",
    response_model=schemas.NewsOut,
    summary="Редактировать новость",
    description="Позволяет автору новости отредактировать её заголовок или содержание.",
    responses={
        403: {"description": "Нет прав для редактирования"},
        404: {"description": "Новость не найдена"},
        422: {"description": "Ошибка валидации"},
    },
)
async def update_news(
    news_id: uuid.UUID,
    req: schemas.NewsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Редактировать новость (только автор)."""
    return await service.update_news(db, news_id, req, current_user.id)


@router.delete(
    "/{news_id}",
    summary="Удалить новость",
    description="Удаляет (снимает с публикации) новость. Доступно только автору.",
    responses={
        403: {"description": "Нет прав для удаления"},
        404: {"description": "Новость не найдена"},
    },
)
async def delete_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить новость (только автор)."""
    return await service.delete_news(db, news_id, current_user.id)
