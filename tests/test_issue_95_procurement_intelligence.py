from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import importlib
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-monolith"))

intelligence_service = importlib.import_module("app.modules.intelligence.service")
ParticipantSnapshot = intelligence_service.ParticipantSnapshot
ProcurementIntelligenceService = intelligence_service.ProcurementIntelligenceService
PurchaseSnapshot = intelligence_service.PurchaseSnapshot
StaticClock = intelligence_service.StaticClock
VoteSnapshot = intelligence_service.VoteSnapshot


NOW = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)


def make_snapshot() -> PurchaseSnapshot:
    candidate_a = uuid.uuid4()
    candidate_b = uuid.uuid4()

    return PurchaseSnapshot(
        id=uuid.uuid4(),
        title="Office supplies group buy",
        status="payment",
        city="Moscow",
        target_amount=Decimal("10000.00"),
        current_amount=Decimal("1500.00"),
        stop_at_amount=Decimal("9000.00"),
        created_at=NOW - timedelta(days=10),
        deadline=NOW + timedelta(days=2),
        supplier_id=None,
        participants=[
            ParticipantSnapshot(
                user_id=uuid.uuid4(),
                quantity=Decimal("5"),
                amount=Decimal("500.00"),
                city="Moscow",
                status="pending",
            ),
            ParticipantSnapshot(
                user_id=uuid.uuid4(),
                quantity=Decimal("3"),
                amount=Decimal("300.00"),
                city="Saint Petersburg",
                status="confirmed",
            ),
            ParticipantSnapshot(
                user_id=uuid.uuid4(),
                quantity=Decimal("7"),
                amount=Decimal("700.00"),
                city="Moscow",
                status="paid",
            ),
            ParticipantSnapshot(
                user_id=uuid.uuid4(),
                quantity=Decimal("1"),
                amount=Decimal("100.00"),
                city="Moscow",
                status="cancelled",
                is_active=False,
            ),
        ],
        votes=[
            VoteSnapshot(candidate_id=candidate_a, value=2),
            VoteSnapshot(candidate_id=candidate_a, value=1),
            VoteSnapshot(candidate_id=candidate_b, value=1),
        ],
    )


def test_intelligence_report_forecasts_high_risk_and_next_actions():
    service = ProcurementIntelligenceService(clock=StaticClock(NOW))

    report = service.build_report(make_snapshot())

    assert report.progress_percent == Decimal("15.00")
    assert report.missing_amount == Decimal("8500.00")
    assert report.velocity.average_daily_amount == Decimal("150.00")
    assert report.velocity.projected_completion_at is not None
    assert report.velocity.projected_completion_at > NOW + timedelta(days=50)
    assert report.risk.level == "high"
    assert "projected_completion_after_deadline" in report.risk.reasons
    assert "low_progress_near_deadline" in report.risk.reasons

    action_codes = {action.code for action in report.actions}
    assert {
        "boost-promotion",
        "confirm-participants",
        "collect-payments",
        "approve-leading-supplier",
    }.issubset(action_codes)


def test_intelligence_report_groups_fulfillment_and_notifications():
    service = ProcurementIntelligenceService(clock=StaticClock(NOW))

    report = service.build_report(make_snapshot())

    assert [batch.city for batch in report.fulfillment.city_batches] == [
        "Moscow",
        "Saint Petersburg",
    ]
    assert report.fulfillment.city_batches[0].participants_count == 2
    assert report.fulfillment.city_batches[0].total_amount == Decimal("1200.00")
    assert report.fulfillment.city_batches[0].total_quantity == Decimal("12.00")
    assert report.fulfillment.status_counts == {
        "confirmed": 1,
        "paid": 1,
        "pending": 1,
    }

    templates = {plan.template_key: plan for plan in report.notification_plan}
    assert "confirm_participation" in templates
    assert "payment_reminder" in templates
    assert "delivery_update" in templates
    assert templates["confirm_participation"].audience_status == "pending"
    assert templates["payment_reminder"].audience_status == "confirmed"
    assert templates["delivery_update"].audience_status == "paid"


def test_intelligence_report_scores_supplier_vote_leaderboard():
    service = ProcurementIntelligenceService(clock=StaticClock(NOW))

    report = service.build_report(make_snapshot())

    assert len(report.supplier_candidates) == 2
    assert report.supplier_candidates[0].total_votes == 2
    assert report.supplier_candidates[0].total_value == 3
    assert report.supplier_candidates[0].confidence_percent == Decimal("75.00")
    assert report.supplier_candidates[1].total_votes == 1
    assert report.supplier_candidates[1].total_value == 1


def test_intelligence_api_is_wired_into_monolith():
    main = (ROOT / "backend-monolith" / "app" / "main.py").read_text(encoding="utf-8")
    router = (
        ROOT / "backend-monolith" / "app" / "modules" / "intelligence" / "router.py"
    ).read_text(encoding="utf-8")

    assert "intelligence_router" in main
    assert "app.include_router(intelligence_router)" in main
    assert 'prefix="/intelligence"' in router
    assert "/purchases/{purchase_id}/report" in router
