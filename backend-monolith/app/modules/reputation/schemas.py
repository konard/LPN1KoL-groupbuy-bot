import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    target_id: uuid.UUID
    purchase_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ReviewOut(BaseModel):
    id: uuid.UUID
    reviewer_id: uuid.UUID
    target_id: uuid.UUID
    purchase_id: uuid.UUID | None
    rating: int
    comment: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
