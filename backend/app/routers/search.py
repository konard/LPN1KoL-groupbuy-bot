"""
Роутер поиска (/api/search/*).
Перенесён из search-service (порт 4007).
"""
from typing import List

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.search import SavedFilterCreate, SavedFilterOut, SearchRequest, SearchResult
from app.services import search_service as svc

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResult)
async def search(data: SearchRequest, user=Depends(get_current_user)):
    """Полнотекстовый поиск закупок через Elasticsearch."""
    await svc.add_to_history(user.id, data.query)
    return await svc.search_purchases(data.query, data.category, data.status, data.page, data.size)


@router.get("/filters", response_model=List[SavedFilterOut])
async def get_filters(user=Depends(get_current_user)):
    """Возвращает сохранённые фильтры поиска текущего пользователя."""
    return await svc.get_filters(user.id)


@router.post("/filters", response_model=SavedFilterOut, status_code=201)
async def save_filter(data: SavedFilterCreate, user=Depends(get_current_user)):
    """Сохраняет фильтр поиска в Redis."""
    return await svc.save_filter(user.id, data.name, data.filters)


@router.delete("/filters/{filter_id}", status_code=204)
async def delete_filter(filter_id: str, user=Depends(get_current_user)):
    """Удаляет сохранённый фильтр."""
    await svc.delete_filter(user.id, filter_id)


@router.get("/history")
async def get_history(user=Depends(get_current_user)):
    """Возвращает историю поисковых запросов пользователя."""
    return {"history": await svc.get_history(user.id)}
