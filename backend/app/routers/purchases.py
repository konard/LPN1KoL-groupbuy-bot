"""
Роутер закупок (/api/purchases/*).
Перенесён из purchase-service (порт 4002).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.purchase import (
    AddCandidateRequest, CandidateOut, CastVoteRequest,
    PurchaseCreate, PurchaseOut, VotingSessionOut,
)
from app.services import purchase_service as svc

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseOut, status_code=201)
async def create_purchase(data: PurchaseCreate, db: Session = Depends(get_db),
                          user=Depends(get_current_user)):
    """Создаёт новую закупку со статусом draft."""
    return svc.create_purchase(
        db, user.id, data.title, data.description,
        data.category, data.min_quantity, data.commission_pct,
    )


@router.get("", response_model=List[PurchaseOut])
def list_purchases(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Возвращает список закупок. Фильтрация по статусу."""
    return svc.list_purchases(db, status, skip, limit)


@router.get("/{purchase_id}", response_model=PurchaseOut)
def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    """Возвращает закупку по ID."""
    return svc.get_purchase(db, purchase_id)


@router.post("/{purchase_id}/voting-sessions", response_model=VotingSessionOut, status_code=201)
async def start_voting(purchase_id: int, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """Запускает сессию голосования. Только для организатора закупки."""
    return await svc.start_voting(db, purchase_id, user.id)


@router.post("/{purchase_id}/voting-sessions/{session_id}/candidates",
             response_model=CandidateOut, status_code=201)
async def add_candidate(purchase_id: int, session_id: int,
                        data: AddCandidateRequest, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    """Добавляет поставщика-кандидата в сессию голосования."""
    return await svc.add_candidate(db, session_id, data.supplier_id, data.price, data.description)


@router.post("/{purchase_id}/voting-sessions/{session_id}/vote")
async def cast_vote(purchase_id: int, session_id: int,
                    data: CastVoteRequest, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    """Голосует за кандидата. При повторном голосовании меняет выбор."""
    return await svc.cast_vote(db, session_id, user.id, data.candidate_id)


@router.post("/{purchase_id}/voting-sessions/{session_id}/close")
async def close_voting(purchase_id: int, session_id: int,
                       db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """Закрывает голосование и определяет победителя."""
    return await svc.close_voting(db, session_id, purchase_id, user.id)


@router.post("/{purchase_id}/cancel")
async def cancel_purchase(purchase_id: int, db: Session = Depends(get_db),
                          user=Depends(get_current_user)):
    """Отменяет закупку. Только для организатора."""
    await svc.cancel_purchase(db, purchase_id, user.id)
    return {"success": True}
