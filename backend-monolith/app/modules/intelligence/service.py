import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol


CENT = Decimal("0.01")


class Clock(Protocol):
    def now(self) -> datetime: ...


class RiskPolicy(Protocol):
    def assess(
        self,
        snapshot: "PurchaseSnapshot",
        progress_percent: Decimal,
        missing_amount: Decimal,
        velocity: "VelocityInsight",
        fulfillment: "FulfillmentPlan",
        now: datetime,
    ) -> "RiskInsight": ...


class ActionPlanner(Protocol):
    def plan(
        self,
        snapshot: "PurchaseSnapshot",
        missing_amount: Decimal,
        risk: "RiskInsight",
        fulfillment: "FulfillmentPlan",
        supplier_candidates: list["SupplierCandidateScore"],
    ) -> list["ActionPlanItem"]: ...


class NotificationPlanner(Protocol):
    def plan(
        self,
        snapshot: "PurchaseSnapshot",
        participants: list["ParticipantSnapshot"],
    ) -> list["NotificationPlanItem"]: ...


class SupplierScorer(Protocol):
    def score(self, votes: list["VoteSnapshot"]) -> list["SupplierCandidateScore"]: ...


class FulfillmentPlanner(Protocol):
    def plan(self, participants: list["ParticipantSnapshot"]) -> "FulfillmentPlan": ...


@dataclass(frozen=True, slots=True)
class StaticClock:
    current_time: datetime

    def now(self) -> datetime:
        return self.current_time


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ParticipantSnapshot:
    user_id: uuid.UUID
    quantity: Decimal
    amount: Decimal
    city: str | None
    status: str
    is_active: bool = True
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VoteSnapshot:
    candidate_id: uuid.UUID | None
    value: int


@dataclass(frozen=True, slots=True)
class PurchaseSnapshot:
    id: uuid.UUID
    title: str
    status: str
    city: str | None
    target_amount: Decimal
    current_amount: Decimal
    stop_at_amount: Decimal | None
    created_at: datetime
    deadline: datetime | None
    supplier_id: uuid.UUID | None = None
    participants: list[ParticipantSnapshot] = field(default_factory=list)
    votes: list[VoteSnapshot] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VelocityInsight:
    average_daily_amount: Decimal
    projected_completion_at: datetime | None
    days_to_completion: int | None
    days_open: int


@dataclass(frozen=True, slots=True)
class RiskInsight:
    level: str
    score: int
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class ActionPlanItem:
    code: str
    title: str
    priority: int
    payload: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CityBatch:
    city: str
    participants_count: int
    total_quantity: Decimal
    total_amount: Decimal


@dataclass(frozen=True, slots=True)
class FulfillmentPlan:
    city_batches: list[CityBatch]
    status_counts: dict[str, int]
    active_participants_count: int
    paid_participants_count: int
    unpaid_participants_count: int


@dataclass(frozen=True, slots=True)
class SupplierCandidateScore:
    candidate_id: uuid.UUID
    total_votes: int
    total_value: int
    confidence_percent: Decimal


@dataclass(frozen=True, slots=True)
class NotificationPlanItem:
    audience_status: str
    template_key: str
    channel: str
    user_ids: list[uuid.UUID]
    reason: str


@dataclass(frozen=True, slots=True)
class ProcurementIntelligenceReport:
    purchase_id: uuid.UUID
    title: str
    generated_at: datetime
    progress_percent: Decimal
    missing_amount: Decimal
    remaining_days: int | None
    velocity: VelocityInsight
    risk: RiskInsight
    actions: list[ActionPlanItem]
    fulfillment: FulfillmentPlan
    supplier_candidates: list[SupplierCandidateScore]
    notification_plan: list[NotificationPlanItem]


class CityFulfillmentPlanner:
    def plan(self, participants: list[ParticipantSnapshot]) -> FulfillmentPlan:
        status_counts: dict[str, int] = {}
        city_totals: dict[str, dict[str, Decimal | int]] = {}

        for participant in participants:
            status_counts[participant.status] = (
                status_counts.get(participant.status, 0) + 1
            )
            city = participant.city or "Unknown"
            bucket = city_totals.setdefault(
                city,
                {
                    "participants_count": 0,
                    "total_quantity": Decimal("0"),
                    "total_amount": Decimal("0"),
                },
            )
            bucket["participants_count"] = int(bucket["participants_count"]) + 1
            bucket["total_quantity"] = (
                Decimal(bucket["total_quantity"]) + participant.quantity
            )
            bucket["total_amount"] = (
                Decimal(bucket["total_amount"]) + participant.amount
            )

        city_batches = [
            CityBatch(
                city=city,
                participants_count=int(totals["participants_count"]),
                total_quantity=_money(Decimal(totals["total_quantity"])),
                total_amount=_money(Decimal(totals["total_amount"])),
            )
            for city, totals in city_totals.items()
        ]
        city_batches.sort(key=lambda batch: (-batch.total_amount, batch.city))

        paid_count = status_counts.get("paid", 0)
        active_count = len(participants)
        return FulfillmentPlan(
            city_batches=city_batches,
            status_counts=dict(sorted(status_counts.items())),
            active_participants_count=active_count,
            paid_participants_count=paid_count,
            unpaid_participants_count=active_count - paid_count,
        )


class WeightedVoteSupplierScorer:
    def score(self, votes: list[VoteSnapshot]) -> list[SupplierCandidateScore]:
        totals: dict[uuid.UUID, dict[str, int]] = {}

        for vote in votes:
            if vote.candidate_id is None:
                continue
            bucket = totals.setdefault(
                vote.candidate_id, {"total_votes": 0, "total_value": 0}
            )
            bucket["total_votes"] += 1
            bucket["total_value"] += vote.value

        total_value = sum(bucket["total_value"] for bucket in totals.values())
        candidates = [
            SupplierCandidateScore(
                candidate_id=candidate_id,
                total_votes=bucket["total_votes"],
                total_value=bucket["total_value"],
                confidence_percent=_percent(bucket["total_value"], total_value),
            )
            for candidate_id, bucket in totals.items()
        ]
        candidates.sort(
            key=lambda item: (
                -item.total_value,
                -item.total_votes,
                str(item.candidate_id),
            )
        )
        return candidates


class DefaultNotificationPlanner:
    def plan(
        self,
        snapshot: PurchaseSnapshot,
        participants: list[ParticipantSnapshot],
    ) -> list[NotificationPlanItem]:
        status_to_users: dict[str, list[uuid.UUID]] = {}
        for participant in participants:
            status_to_users.setdefault(participant.status, []).append(
                participant.user_id
            )

        plans: list[NotificationPlanItem] = []
        if status_to_users.get("pending"):
            plans.append(
                NotificationPlanItem(
                    audience_status="pending",
                    template_key="confirm_participation",
                    channel="push",
                    user_ids=status_to_users["pending"],
                    reason="Participants need to confirm before payment collection.",
                )
            )
        if snapshot.status in {"stopped", "payment"} and status_to_users.get(
            "confirmed"
        ):
            plans.append(
                NotificationPlanItem(
                    audience_status="confirmed",
                    template_key="payment_reminder",
                    channel="push",
                    user_ids=status_to_users["confirmed"],
                    reason="Confirmed participants have not completed payment yet.",
                )
            )
        if snapshot.status in {"payment", "completed"} and status_to_users.get("paid"):
            plans.append(
                NotificationPlanItem(
                    audience_status="paid",
                    template_key="delivery_update",
                    channel="push",
                    user_ids=status_to_users["paid"],
                    reason="Paid participants should receive delivery progress updates.",
                )
            )
        return plans


class DefaultActionPlanner:
    def plan(
        self,
        snapshot: PurchaseSnapshot,
        missing_amount: Decimal,
        risk: RiskInsight,
        fulfillment: FulfillmentPlan,
        supplier_candidates: list[SupplierCandidateScore],
    ) -> list[ActionPlanItem]:
        actions: list[ActionPlanItem] = []
        status_counts = fulfillment.status_counts

        if missing_amount > 0 and risk.level in {"medium", "high"}:
            actions.append(
                ActionPlanItem(
                    code="boost-promotion",
                    title="Increase promotion for the purchase",
                    priority=10,
                    payload={"missing_amount": str(missing_amount)},
                )
            )
        if status_counts.get("pending", 0) > 0:
            actions.append(
                ActionPlanItem(
                    code="confirm-participants",
                    title="Ask pending participants to confirm quantities",
                    priority=20,
                    payload={"participants": str(status_counts["pending"])},
                )
            )
        if (
            snapshot.status in {"stopped", "payment"}
            and fulfillment.unpaid_participants_count > 0
        ):
            actions.append(
                ActionPlanItem(
                    code="collect-payments",
                    title="Send payment reminders to unpaid participants",
                    priority=30,
                    payload={
                        "participants": str(fulfillment.unpaid_participants_count)
                    },
                )
            )
        if supplier_candidates and snapshot.supplier_id is None:
            actions.append(
                ActionPlanItem(
                    code="approve-leading-supplier",
                    title="Review the leading supplier candidate",
                    priority=35,
                    payload={"candidate_id": str(supplier_candidates[0].candidate_id)},
                )
            )
        if (
            not supplier_candidates
            and snapshot.supplier_id is None
            and snapshot.status in {"active", "stopped", "payment"}
        ):
            actions.append(
                ActionPlanItem(
                    code="start-supplier-vote",
                    title="Start supplier selection vote",
                    priority=40,
                )
            )
        if fulfillment.paid_participants_count > 0 and snapshot.status in {
            "payment",
            "completed",
        }:
            actions.append(
                ActionPlanItem(
                    code="schedule-delivery",
                    title="Prepare delivery batches for paid participants",
                    priority=50,
                    payload={"participants": str(fulfillment.paid_participants_count)},
                )
            )

        return sorted(actions, key=lambda action: (action.priority, action.code))


class DefaultRiskPolicy:
    def assess(
        self,
        snapshot: PurchaseSnapshot,
        progress_percent: Decimal,
        missing_amount: Decimal,
        velocity: VelocityInsight,
        fulfillment: FulfillmentPlan,
        now: datetime,
    ) -> RiskInsight:
        reasons: list[str] = []
        score = 0

        if snapshot.status == "cancelled":
            return RiskInsight(level="high", score=100, reasons=["purchase_cancelled"])

        if missing_amount <= 0:
            return RiskInsight(level="low", score=0, reasons=["target_reached"])

        if fulfillment.active_participants_count == 0:
            score += 35
            reasons.append("no_active_participants")

        if progress_percent < Decimal("25.00"):
            score += 15
            reasons.append("low_progress")

        if snapshot.deadline is not None:
            deadline = _aware(snapshot.deadline)
            remaining_days = _days_between(now, deadline)
            if remaining_days < 0:
                score += 50
                reasons.append("deadline_passed")
            elif remaining_days <= 3 and progress_percent < Decimal("50.00"):
                score += 30
                reasons.append("low_progress_near_deadline")
            if (
                velocity.projected_completion_at is not None
                and velocity.projected_completion_at > deadline
            ):
                score += 40
                reasons.append("projected_completion_after_deadline")

        if snapshot.status == "payment" and fulfillment.unpaid_participants_count > 0:
            score += 20
            reasons.append("unpaid_participants_in_payment_stage")

        if fulfillment.status_counts.get("pending", 0) > fulfillment.status_counts.get(
            "paid", 0
        ):
            score += 10
            reasons.append("pending_participants_exceed_paid")

        capped_score = min(score, 100)
        if capped_score >= 60:
            level = "high"
        elif capped_score >= 25:
            level = "medium"
        else:
            level = "low"
        return RiskInsight(level=level, score=capped_score, reasons=reasons)


class ProcurementIntelligenceService:
    def __init__(
        self,
        clock: Clock | None = None,
        fulfillment_planner: FulfillmentPlanner | None = None,
        supplier_scorer: SupplierScorer | None = None,
        notification_planner: NotificationPlanner | None = None,
        action_planner: ActionPlanner | None = None,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self.clock = clock or SystemClock()
        self.fulfillment_planner = fulfillment_planner or CityFulfillmentPlanner()
        self.supplier_scorer = supplier_scorer or WeightedVoteSupplierScorer()
        self.notification_planner = notification_planner or DefaultNotificationPlanner()
        self.action_planner = action_planner or DefaultActionPlanner()
        self.risk_policy = risk_policy or DefaultRiskPolicy()

    def build_report(self, snapshot: PurchaseSnapshot) -> ProcurementIntelligenceReport:
        now = _aware(self.clock.now())
        active_participants = [
            participant
            for participant in snapshot.participants
            if participant.is_active and participant.status != "cancelled"
        ]
        missing_amount = max(
            snapshot.target_amount - snapshot.current_amount, Decimal("0")
        )
        progress_percent = _percent(snapshot.current_amount, snapshot.target_amount)
        velocity = _build_velocity(snapshot, missing_amount, now)
        fulfillment = self.fulfillment_planner.plan(active_participants)
        supplier_candidates = self.supplier_scorer.score(snapshot.votes)
        risk = self.risk_policy.assess(
            snapshot=snapshot,
            progress_percent=progress_percent,
            missing_amount=missing_amount,
            velocity=velocity,
            fulfillment=fulfillment,
            now=now,
        )
        actions = self.action_planner.plan(
            snapshot=snapshot,
            missing_amount=_money(missing_amount),
            risk=risk,
            fulfillment=fulfillment,
            supplier_candidates=supplier_candidates,
        )
        notification_plan = self.notification_planner.plan(
            snapshot, active_participants
        )

        return ProcurementIntelligenceReport(
            purchase_id=snapshot.id,
            title=snapshot.title,
            generated_at=now,
            progress_percent=progress_percent,
            missing_amount=_money(missing_amount),
            remaining_days=_remaining_days(snapshot.deadline, now),
            velocity=velocity,
            risk=risk,
            actions=actions,
            fulfillment=fulfillment,
            supplier_candidates=supplier_candidates,
            notification_plan=notification_plan,
        )


def _build_velocity(
    snapshot: PurchaseSnapshot,
    missing_amount: Decimal,
    now: datetime,
) -> VelocityInsight:
    created_at = _aware(snapshot.created_at)
    days_open = max(1, _days_between(created_at, now))
    average_daily_amount = _money(snapshot.current_amount / Decimal(days_open))

    if missing_amount <= 0:
        return VelocityInsight(
            average_daily_amount=average_daily_amount,
            projected_completion_at=now,
            days_to_completion=0,
            days_open=days_open,
        )
    if average_daily_amount <= 0:
        return VelocityInsight(
            average_daily_amount=Decimal("0.00"),
            projected_completion_at=None,
            days_to_completion=None,
            days_open=days_open,
        )

    days_to_completion = math.ceil(missing_amount / average_daily_amount)
    return VelocityInsight(
        average_daily_amount=average_daily_amount,
        projected_completion_at=now + timedelta(days=days_to_completion),
        days_to_completion=days_to_completion,
        days_open=days_open,
    )


def _remaining_days(deadline: datetime | None, now: datetime) -> int | None:
    if deadline is None:
        return None
    return _days_between(now, _aware(deadline))


def _days_between(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    return math.ceil(seconds / 86400)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _percent(numerator: Decimal | int, denominator: Decimal | int) -> Decimal:
    denominator_decimal = Decimal(denominator)
    if denominator_decimal <= 0:
        return Decimal("0.00")
    value = Decimal(numerator) / denominator_decimal * Decimal("100")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
