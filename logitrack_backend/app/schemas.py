from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    """Request body for creating an order."""

    destination: str = Field(min_length=1, max_length=300)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"destination": "12 Market Street, loading dock B"}]
        }
    )


class AssignCourier(BaseModel):
    """Request body for assigning a courier."""

    courier_id: str = Field(min_length=1, max_length=80)

    model_config = ConfigDict(json_schema_extra={"examples": [{"courier_id": "c-42"}]})


class OrderRead(BaseModel):
    """Serialized order response."""

    id: int
    destination: str
    courier_id: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    """Health check response."""

    status: str
    database: bool
    redis: bool
