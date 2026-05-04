"""
Бизнес-логика закупок: CRUD, голосование, отмена.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.clients.kafka_client import publish
from app.models.purchase import CandidateModel, PurchaseModel, VoteModel, VotingSessionModel

logger = logging.getLogger(__name__)


def create_purchase(db: Session, organizer_id: int, title: str, description: str | None,
                    category: str | None, min_quantity: int, commission_pct: float) -> PurchaseModel:
    """Создаёт новую закупку со статусом 'draft'."""
    purchase = PurchaseModel(
        organizer_id=organizer_id,
        title=title,
        description=description,
        category=category,
        min_quantity=min_quantity,
        commission_pct=commission_pct,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase


def list_purchases(db: Session, status: str | None = None, skip: int = 0, limit: int = 50):
    """Возвращает список закупок с фильтрацией по статусу."""
    q = db.query(PurchaseModel)
    if status:
        q = q.filter(PurchaseModel.status == status)
    return q.order_by(PurchaseModel.created_at.desc()).offset(skip).limit(limit).all()


def get_purchase(db: Session, purchase_id: int) -> PurchaseModel:
    """Возвращает закупку по ID или бросает 404."""
    purchase = db.query(PurchaseModel).filter(PurchaseModel.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Закупка не найдена")
    return purchase


async def start_voting(db: Session, purchase_id: int, user_id: int) -> VotingSessionModel:
    """Начинает сессию голосования. Только организатор может запустить."""
    purchase = get_purchase(db, purchase_id)
    if purchase.organizer_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только организатор может начать голосование")

    session = VotingSessionModel(purchase_id=purchase_id)
    db.add(session)
    purchase.status = "voting"
    purchase.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    await publish("purchase.voting.started", {
        "purchaseId": purchase_id, "sessionId": session.id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return session


async def add_candidate(db: Session, session_id: int, supplier_id: int,
                        price: float, description: str | None) -> CandidateModel:
    """Добавляет поставщика-кандидата в сессию голосования."""
    candidate = CandidateModel(
        session_id=session_id,
        supplier_id=supplier_id,
        price=price,
        description=description,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


async def cast_vote(db: Session, session_id: int, user_id: int, candidate_id: int) -> dict:
    """Голосует за кандидата. Если уже голосовал — меняет голос."""
    existing = db.query(VoteModel).filter(
        VoteModel.session_id == session_id,
        VoteModel.user_id == user_id,
    ).first()

    if existing:
        existing.candidate_id = candidate_id
        db.commit()
        return {"action": "changed"}

    vote = VoteModel(session_id=session_id, user_id=user_id, candidate_id=candidate_id)
    db.add(vote)
    db.commit()
    return {"action": "cast"}


async def close_voting(db: Session, session_id: int, purchase_id: int, user_id: int) -> dict:
    """
    Закрывает голосование. Определяет победителя (максимум голосов).
    При ничьей — статус 'tie'.
    """
    purchase = get_purchase(db, purchase_id)
    if purchase.organizer_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только организатор может закрыть голосование")

    session = db.query(VotingSessionModel).filter(VotingSessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")

    from sqlalchemy import func
    results = (
        db.query(VoteModel.candidate_id, func.count(VoteModel.id).label("cnt"))
        .filter(VoteModel.session_id == session_id)
        .group_by(VoteModel.candidate_id)
        .order_by(func.count(VoteModel.id).desc())
        .all()
    )

    if not results:
        session.status = "closed"
        db.commit()
        return {"winnerId": None, "totalVotes": 0}

    winner_id = results[0].candidate_id
    total_votes = sum(r.cnt for r in results)
    is_tie = len(results) > 1 and results[0].cnt == results[1].cnt

    session.status = "tie" if is_tie else "closed"
    session.winner_id = winner_id
    session.closed_at = datetime.now(timezone.utc)
    db.commit()

    event = "purchase.voting.tie" if is_tie else "purchase.voting.closed"
    await publish(event, {
        "purchaseId": purchase_id, "sessionId": session_id,
        "winnerId": winner_id, "totalVotes": total_votes,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return {"winnerId": winner_id, "totalVotes": total_votes, "isTie": is_tie}


async def cancel_purchase(db: Session, purchase_id: int, user_id: int) -> None:
    """Отменяет закупку. Только организатор может отменить."""
    purchase = get_purchase(db, purchase_id)
    if purchase.organizer_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только организатор может отменить закупку")
    purchase.status = "cancelled"
    purchase.updated_at = datetime.now(timezone.utc)
    db.commit()
    await publish("purchase.cancelled", {
        "purchaseId": purchase_id, "userId": user_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
