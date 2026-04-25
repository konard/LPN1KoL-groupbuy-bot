import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.intelligence.repository import SqlAlchemyPurchaseSnapshotRepository
from app.modules.intelligence.schemas import ProcurementIntelligenceReportOut
from app.modules.intelligence.service import ProcurementIntelligenceService


router = APIRouter(prefix="/intelligence", tags=["Procurement intelligence"])


@router.get(
    "/purchases/{purchase_id}/report",
    response_model=ProcurementIntelligenceReportOut,
    summary="Procurement intelligence report",
    description=(
        "Builds an operational intelligence report for a purchase: completion forecast, "
        "risk factors, recommended organizer actions, fulfillment batches, supplier "
        "vote leaderboard, and notification audiences."
    ),
    responses={404: {"description": "Purchase not found"}},
)
async def purchase_intelligence_report(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    repository = SqlAlchemyPurchaseSnapshotRepository(db)
    snapshot = await repository.get_snapshot(purchase_id)
    report = ProcurementIntelligenceService().build_report(snapshot)
    return ProcurementIntelligenceReportOut.model_validate(report)
