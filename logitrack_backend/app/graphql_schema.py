from datetime import datetime

import strawberry
from sqlalchemy import select
from strawberry.types import Info

from .models import OrderHistory


@strawberry.type
class OrderStatusEntry:
    status: str
    created_at: datetime


@strawberry.type
class Query:
    @strawberry.field
    async def order_history(self, info: Info, order_id: int) -> list[OrderStatusEntry]:
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


schema = strawberry.Schema(query=Query)
