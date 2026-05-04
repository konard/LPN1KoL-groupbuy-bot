"""
Бизнес-логика репутации: отзывы, жалобы, автоблокировка.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clients.kafka_client import publish
from app.models.reputation import ComplaintModel, ReputationScoreModel, ReviewModel
from app.models.user import UserModel

logger = logging.getLogger(__name__)

# Порог автоматической блокировки пользователя
AUTO_BLOCK_THRESHOLD = 5


def _get_or_create_score(db: Session, user_id: int) -> ReputationScoreModel:
    """Возвращает репутационный профиль пользователя, создаёт при первом обращении."""
    score = db.query(ReputationScoreModel).filter(ReputationScoreModel.user_id == user_id).first()
    if not score:
        score = ReputationScoreModel(user_id=user_id)
        db.add(score)
        db.commit()
        db.refresh(score)
    return score


def _recalculate_score(db: Session, user_id: int) -> None:
    """Пересчитывает средний рейтинг пользователя по всем отзывам."""
    result = db.query(func.avg(ReviewModel.rating)).filter(ReviewModel.target_id == user_id).scalar()
    total = db.query(func.count(ReviewModel.id)).filter(ReviewModel.target_id == user_id).scalar()
    score = _get_or_create_score(db, user_id)
    score.score = Decimal(str(round(result, 2))) if result else Decimal("0.00")
    score.total_reviews = total or 0
    score.updated_at = datetime.now(timezone.utc)
    db.commit()


async def create_review(db: Session, author_id: int, target_id: int, purchase_id: int | None,
                        rating: int, comment: str, is_anonymous: bool) -> ReviewModel:
    """Создаёт отзыв и пересчитывает репутационный балл цели."""
    review = ReviewModel(
        author_id=author_id,
        target_id=target_id,
        purchase_id=purchase_id,
        rating=rating,
        comment=comment,
        is_anonymous=is_anonymous,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    _recalculate_score(db, target_id)

    await publish("review.created", {
        "reviewId": review.id, "authorId": author_id, "targetId": target_id,
        "rating": rating, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return review


async def file_complaint(db: Session, reporter_id: int, target_id: int, purchase_id: int | None,
                          reason: str, evidence_url: str | None) -> ComplaintModel:
    """Подаёт жалобу. Проверяет порог автоблокировки после создания."""
    complaint = ComplaintModel(
        reporter_id=reporter_id,
        target_id=target_id,
        purchase_id=purchase_id,
        reason=reason,
        evidence_url=evidence_url,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # Обновляем счётчик жалоб
    score = _get_or_create_score(db, target_id)
    score.total_complaints += 1

    # Автоблокировка при превышении порога нерешённых жалоб
    open_count = db.query(func.count(ComplaintModel.id)).filter(
        ComplaintModel.target_id == target_id,
        ComplaintModel.status == "open",
    ).scalar()

    if open_count >= AUTO_BLOCK_THRESHOLD and not score.is_blocked:
        score.is_blocked = True
        user = db.query(UserModel).filter(UserModel.id == target_id).first()
        if user:
            user.is_blocked = True
        await publish("user.auto_blocked", {
            "userId": target_id, "openComplaints": open_count,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Пользователь %d автоматически заблокирован (%d жалоб)", target_id, open_count)

    db.commit()

    await publish("complaint.filed", {
        "complaintId": complaint.id, "reporterId": reporter_id,
        "targetId": target_id, "ts": datetime.now(timezone.utc).isoformat(),
    })
    return complaint


async def resolve_complaint(db: Session, complaint_id: int, new_status: str,
                             resolution: str | None) -> ComplaintModel:
    """Разрешает жалобу (только администраторы)."""
    complaint = db.query(ComplaintModel).filter(ComplaintModel.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Жалоба не найдена")
    complaint.status = new_status
    complaint.resolution = resolution
    complaint.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(complaint)

    await publish("complaint.resolved", {
        "complaintId": complaint_id, "status": new_status,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return complaint


def get_score(db: Session, user_id: int) -> ReputationScoreModel:
    """Возвращает репутационный балл пользователя."""
    return _get_or_create_score(db, user_id)
