import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.intelligence.service import (
    ParticipantSnapshot,
    PurchaseSnapshot,
    VoteSnapshot,
)
from app.modules.purchase.models import Participant, Purchase, Vote


class SqlAlchemyPurchaseSnapshotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_snapshot(self, purchase_id: uuid.UUID) -> PurchaseSnapshot:
        purchase = await self.db.get(Purchase, purchase_id)
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")

        participants_result = await self.db.execute(
            select(Participant).where(Participant.purchase_id == purchase_id)
        )
        votes_result = await self.db.execute(
            select(Vote).where(Vote.purchase_id == purchase_id)
        )

        return PurchaseSnapshot(
            id=purchase.id,
            title=purchase.title,
            status=purchase.status,
            city=purchase.city,
            target_amount=purchase.target_amount,
            current_amount=purchase.current_amount,
            stop_at_amount=purchase.stop_at_amount,
            created_at=purchase.created_at,
            deadline=purchase.deadline,
            supplier_id=purchase.supplier_id,
            participants=[
                ParticipantSnapshot(
                    user_id=participant.user_id,
                    quantity=participant.quantity,
                    amount=participant.amount,
                    city=participant.city,
                    status=participant.status,
                    is_active=participant.is_active,
                    created_at=participant.created_at,
                )
                for participant in participants_result.scalars().all()
            ],
            votes=[
                VoteSnapshot(candidate_id=vote.candidate_id, value=vote.value)
                for vote in votes_result.scalars().all()
            ],
        )
