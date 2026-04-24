from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    destination: str = Field(min_length=1, max_length=300)


class AssignCourier(BaseModel):
    courier_id: str = Field(min_length=1, max_length=80)


class OrderRead(BaseModel):
    id: int
    destination: str
    courier_id: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
