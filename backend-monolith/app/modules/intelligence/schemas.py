import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class VelocityInsightOut(BaseModel):
    average_daily_amount: Decimal = Field(
        ..., description="Average collected amount per day"
    )
    projected_completion_at: datetime | None = Field(
        None, description="Projected time when the target amount will be reached"
    )
    days_to_completion: int | None = Field(
        None, description="Estimated number of days until the target amount is reached"
    )
    days_open: int = Field(
        ..., description="Number of days since the purchase was created"
    )

    model_config = {"from_attributes": True}


class RiskInsightOut(BaseModel):
    level: str = Field(..., description="Risk level: low | medium | high")
    score: int = Field(..., ge=0, le=100, description="Risk score from 0 to 100")
    reasons: list[str] = Field(default_factory=list, description="Risk factor codes")

    model_config = {"from_attributes": True}


class ActionPlanItemOut(BaseModel):
    code: str = Field(..., description="Stable action code for UI and automation")
    title: str = Field(..., description="Human-readable action title")
    priority: int = Field(..., description="Lower number means higher priority")
    payload: dict[str, str] = Field(default_factory=dict, description="Action context")

    model_config = {"from_attributes": True}


class CityBatchOut(BaseModel):
    city: str = Field(..., description="Delivery city")
    participants_count: int = Field(..., description="Number of active participants")
    total_quantity: Decimal = Field(..., description="Total ordered quantity")
    total_amount: Decimal = Field(..., description="Total committed amount")

    model_config = {"from_attributes": True}


class FulfillmentPlanOut(BaseModel):
    city_batches: list[CityBatchOut] = Field(
        default_factory=list, description="Delivery batches grouped by city"
    )
    status_counts: dict[str, int] = Field(
        default_factory=dict, description="Active participants grouped by status"
    )
    active_participants_count: int = Field(..., description="Active participants total")
    paid_participants_count: int = Field(
        ..., description="Participants with paid status"
    )
    unpaid_participants_count: int = Field(..., description="Participants not yet paid")

    model_config = {"from_attributes": True}


class SupplierCandidateScoreOut(BaseModel):
    candidate_id: uuid.UUID = Field(..., description="Supplier candidate identifier")
    total_votes: int = Field(..., description="Number of votes for the candidate")
    total_value: int = Field(..., description="Weighted vote score")
    confidence_percent: Decimal = Field(
        ..., description="Candidate share of total weighted votes"
    )

    model_config = {"from_attributes": True}


class NotificationPlanItemOut(BaseModel):
    audience_status: str = Field(
        ..., description="Participant status selected for the message"
    )
    template_key: str = Field(..., description="Notification template key")
    channel: str = Field(..., description="Preferred delivery channel")
    user_ids: list[uuid.UUID] = Field(
        default_factory=list, description="Audience user IDs"
    )
    reason: str = Field(..., description="Why this notification should be sent")

    model_config = {"from_attributes": True}


class ProcurementIntelligenceReportOut(BaseModel):
    purchase_id: uuid.UUID = Field(..., description="Purchase identifier")
    title: str = Field(..., description="Purchase title")
    generated_at: datetime = Field(..., description="Report generation timestamp")
    progress_percent: Decimal = Field(..., description="Current collection progress")
    missing_amount: Decimal = Field(..., description="Amount remaining to reach target")
    remaining_days: int | None = Field(None, description="Days until deadline")
    velocity: VelocityInsightOut
    risk: RiskInsightOut
    actions: list[ActionPlanItemOut] = Field(default_factory=list)
    fulfillment: FulfillmentPlanOut
    supplier_candidates: list[SupplierCandidateScoreOut] = Field(default_factory=list)
    notification_plan: list[NotificationPlanItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
