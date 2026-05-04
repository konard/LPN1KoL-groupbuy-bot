"""
Роутер репутации (/api/reputation/*).
Перенесён из reputation-service (порт 4008).
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.schemas.reputation import (
    ComplaintOut, CreateReviewRequest, FileComplaintRequest,
    ReputationScoreOut, ResolveComplaintRequest, ReviewOut,
)
from app.services import reputation_service as svc

router = APIRouter(prefix="/api/reputation", tags=["reputation"])


@router.post("/reviews", response_model=ReviewOut, status_code=201)
async def create_review(data: CreateReviewRequest, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    """Оставляет отзыв с оценкой (1-5). Пересчитывает репутацию цели."""
    return await svc.create_review(
        db, user.id, data.target_id, data.purchase_id,
        data.rating, data.comment or "", data.is_anonymous,
    )


@router.get("/reviews/{user_id}", response_model=List[ReviewOut])
def get_reviews(user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Возвращает все отзывы о пользователе. Скрывает автора анонимных отзывов."""
    from app.models.reputation import ReviewModel
    reviews = db.query(ReviewModel).filter(ReviewModel.target_id == user_id).all()
    result = []
    for r in reviews:
        result.append({
            "id": r.id,
            "author_id": None if r.is_anonymous else r.author_id,
            "target_id": r.target_id,
            "purchase_id": r.purchase_id,
            "rating": r.rating,
            "comment": r.comment,
            "is_anonymous": r.is_anonymous,
            "created_at": r.created_at,
        })
    return result


@router.post("/complaints", response_model=ComplaintOut, status_code=201)
async def file_complaint(data: FileComplaintRequest, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    """Подаёт жалобу на пользователя. При 5+ нерешённых жалобах — автоблокировка."""
    return await svc.file_complaint(
        db, user.id, data.target_id, data.purchase_id,
        data.reason, data.evidence_url,
    )


@router.patch("/complaints/{complaint_id}/resolve", response_model=ComplaintOut)
async def resolve_complaint(complaint_id: int, data: ResolveComplaintRequest,
                             db: Session = Depends(get_db),
                             admin=Depends(get_admin_user)):
    """Разрешает жалобу (только для администраторов)."""
    return await svc.resolve_complaint(db, complaint_id, data.status, data.resolution)


@router.get("/scores/{user_id}", response_model=ReputationScoreOut)
def get_score(user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Возвращает репутационный балл пользователя."""
    score = svc.get_score(db, user_id)
    return {
        "user_id": score.user_id,
        "score": float(score.score),
        "total_reviews": score.total_reviews,
        "total_complaints": score.total_complaints,
        "is_blocked": score.is_blocked,
        "updated_at": score.updated_at,
    }
