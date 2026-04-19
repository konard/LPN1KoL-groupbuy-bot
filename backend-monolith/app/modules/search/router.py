from fastapi import APIRouter, Depends, Query

from app.kafka.producer import emit_event
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.search import service
from app.modules.search.schemas import SearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    result = await service.search_purchases(q, page=page, per_page=per_page)
    await emit_event(
        "search.query",
        str(current_user.id),
        {"q": q, "page": page, "per_page": per_page, "total": result["total"]},
    )
    return result
