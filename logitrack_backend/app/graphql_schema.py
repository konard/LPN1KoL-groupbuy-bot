from datetime import datetime

import strawberry
from sqlalchemy import select
from strawberry.scalars import JSON
from strawberry.types import Info

from .models import CoordinateHistory, OrderHistory


@strawberry.type
class OrderStatusEntry:
    """GraphQL status history entry."""

    status: str
    created_at: datetime


@strawberry.type
class GeoJSONPoint:
    """GeoJSON point geometry."""

    type: str
    coordinates: list[float]


@strawberry.type
class GeoJSONFeature:
    """GeoJSON feature for one coordinate."""

    type: str
    geometry: GeoJSONPoint
    properties: JSON


@strawberry.type
class GeoJSONFeatureCollection:
    """GeoJSON feature collection for an order track."""

    type: str
    features: list[GeoJSONFeature]


@strawberry.type
class Query:
    """GraphQL query root."""

    @strawberry.field
    async def order_history(self, info: Info, order_id: int) -> list[OrderStatusEntry]:
        """Return order status history."""

        session = info.context["session"]
        result = await session.execute(
            select(OrderHistory)
            .where(OrderHistory.order_id == order_id)
            .order_by(OrderHistory.created_at)
        )
        return [
            OrderStatusEntry(status=item.status, created_at=item.created_at)
            for item in result.scalars().all()
        ]

    @strawberry.field
    async def track(self, info: Info, order_id: int) -> GeoJSONFeatureCollection:
        """Return recorded order coordinates as GeoJSON."""

        session = info.context["session"]
        result = await session.execute(
            select(CoordinateHistory)
            .where(CoordinateHistory.order_id == order_id)
            .order_by(CoordinateHistory.sequence)
        )
        features = [
            GeoJSONFeature(
                type="Feature",
                geometry=GeoJSONPoint(
                    type="Point",
                    coordinates=[item.lng, item.lat],
                ),
                properties={
                    "order_id": item.order_id,
                    "sequence": item.sequence,
                    "created_at": item.created_at.isoformat(),
                },
            )
            for item in result.scalars().all()
        ]
        return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


schema = strawberry.Schema(query=Query)
