import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.models import News
from app.modules.news.schemas import NewsCreate, NewsUpdate


async def create_news(db: AsyncSession, req: NewsCreate, author_id: uuid.UUID) -> News:
    news = News(
        author_id=author_id,
        title=req.title,
        content=req.content,
    )
    db.add(news)
    await db.commit()
    await db.refresh(news)
    return news


async def list_news(db: AsyncSession, skip: int = 0, limit: int = 20) -> list[News]:
    result = await db.execute(
        select(News)
        .where(News.is_published.is_(True))
        .order_by(News.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_news(db: AsyncSession, news_id: uuid.UUID) -> News | None:
    return await db.get(News, news_id)


async def update_news(
    db: AsyncSession, news_id: uuid.UUID, req: NewsUpdate, author_id: uuid.UUID
) -> News:
    news = await db.get(News, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Новость не найдена")
    if news.author_id != author_id:
        raise HTTPException(status_code=403, detail="Нет прав для редактирования этой новости")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(news, field, value)
    await db.commit()
    await db.refresh(news)
    return news


async def delete_news(
    db: AsyncSession, news_id: uuid.UUID, author_id: uuid.UUID
) -> dict:
    news = await db.get(News, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Новость не найдена")
    if news.author_id != author_id:
        raise HTTPException(status_code=403, detail="Нет прав для удаления этой новости")
    news.is_published = False
    await db.commit()
    return {"detail": "Новость удалена"}
