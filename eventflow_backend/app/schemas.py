from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    venue: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    price_cents: int = Field(gt=0)
    tickets_available: int = Field(ge=0)


class EventRead(BaseModel):
    id: int
    title: str
    description: str
    venue: str
    starts_at: datetime
    price_cents: int
    tickets_available: int

    model_config = ConfigDict(from_attributes=True)


class TicketPurchase(BaseModel):
    event_id: int
    buyer_email: str = Field(min_length=3, max_length=320)
    card_number: str = Field(min_length=12, max_length=32)


class TicketRead(BaseModel):
    id: int
    event_id: int
    buyer_email: str
    task_id: str
    status: str
    file_path: str | None

    model_config = ConfigDict(from_attributes=True)


class TicketStatus(BaseModel):
    task_id: str
    celery_state: str
    ticket_status: str
    file_path: str | None
