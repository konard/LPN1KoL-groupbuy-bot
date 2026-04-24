from fastapi import APIRouter, Depends, Query

from app.kafka.producer import emit_event
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.search import service
from app.modules.search.schemas import SearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["Поиск"])


@router.get(
    "",
    response_model=SearchResponse,
    summary="Поиск товаров и закупок",
    description=(
        "Позволяет покупателю искать товары по названию. "
        "При вводе названия товара происходит поиск в базе закупок. "
        "Поддерживает полнотекстовый поиск с нечётким соответствием (Elasticsearch). "
        "Результаты включают подсветку совпадений."
    ),
    responses={422: {"description": "Ошибка валидации параметров"}},
)
async def search(
    q: str = Query(..., min_length=1, description="Поисковый запрос (название товара или закупки)", example="мука пшеничная"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(20, ge=1, le=100, description="Количество результатов на странице"),
    current_user: User = Depends(get_current_user),
):
    """Поиск товаров и закупок по ключевому слову."""
    result = await service.search_purchases(q, page=page, per_page=per_page)
    await emit_event(
        "search.query",
        str(current_user.id),
        {"q": q, "page": page, "per_page": per_page, "total": result["total"]},
    )
    return result
