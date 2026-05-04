"""
Pydantic-схемы для модуля поиска.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Запрос полнотекстового поиска закупок."""
    query: str
    category: Optional[str] = None
    status: Optional[str] = None
    # Пагинация
    page: int = 1
    size: int = 20


class SavedFilterCreate(BaseModel):
    """Сохранение фильтра поиска."""
    name: str
    filters: Dict[str, Any]


class SavedFilterOut(BaseModel):
    """Сохранённый фильтр."""
    id: str
    name: str
    filters: Dict[str, Any]


class SearchResult(BaseModel):
    """Результат поиска."""
    total: int
    page: int
    size: int
    items: List[Dict[str, Any]]
