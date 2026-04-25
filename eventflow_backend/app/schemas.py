from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    """Credentials for issuing a demo JWT."""

    subject: str = Field(min_length=1, max_length=80)
    role: Literal["organizer", "user"]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"subject": "organizer-1", "role": "organizer"}]
        }
    )


class TokenResponse(BaseModel):
    """JWT response for API clients."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class Actor(BaseModel):
    """Authenticated actor extracted from a JWT."""

    subject: str
    role: Literal["organizer", "user"]


class EventCreate(BaseModel):
    """Request body for creating an event."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    venue: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    price_cents: int = Field(gt=0)
    tickets_available: int = Field(ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Python Backend Summit",
                    "description": "Async services and distributed systems talks.",
                    "venue": "Tech Hall",
                    "starts_at": "2026-05-10T18:30:00Z",
                    "price_cents": 4900,
                    "tickets_available": 120,
                }
            ]
        }
    )


class EventRead(BaseModel):
    """Serialized event response."""

    id: int
    organizer_id: str
    title: str
    description: str
    venue: str
    starts_at: datetime
    price_cents: int
    tickets_available: int

    model_config = ConfigDict(from_attributes=True)


class TicketPurchase(BaseModel):
    """Request body for purchasing a ticket."""

    event_id: int = Field(gt=0)
    buyer_email: str = Field(min_length=3, max_length=320)
    card_number: str = Field(min_length=12, max_length=32)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event_id": 1,
                    "buyer_email": "guest@example.com",
                    "card_number": "4242424242424242",
                }
            ]
        }
    )


class TicketReturnRequest(BaseModel):
    """Request body for returning a ticket."""

    reason: str = Field(min_length=3, max_length=240)

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"reason": "Schedule conflict"}]}
    )


class TicketRead(BaseModel):
    """Serialized ticket response."""

    id: int
    event_id: int
    buyer_id: str
    buyer_email: str
    task_id: str
    status: str
    file_path: str | None
    returned_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TicketStatus(BaseModel):
    """Background ticket generation status."""

    task_id: str
    celery_state: str
    ticket_status: str
    file_path: str | None


class HealthRead(BaseModel):
    """Health check response."""

    status: Literal["ok", "degraded"]
    database: bool
    redis: bool
    broker: bool
