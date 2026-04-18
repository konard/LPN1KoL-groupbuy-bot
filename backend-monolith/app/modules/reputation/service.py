import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka_producer import publish
from app.modules.reputation.models import Review
from app.modules.reputation.schemas import ReviewCreate


async def create_review(
    db: AsyncSession, req: ReviewCreate, reviewer_id: uuid.UUID
) -> Review:
    review = Review(
        reviewer_id=reviewer_id,
        target_id=req.target_id,
        purchase_id=req.purchase_id,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    await publish(
        "monolith.reputation.review_created",
        {
            "review_id": str(review.id),
            "target_id": str(req.target_id),
            "rating": req.rating,
        },
    )
    return review


async def list_reviews(db: AsyncSession, target_id: uuid.UUID) -> list[Review]:
    result = await db.execute(select(Review).where(Review.target_id == target_id))
    return list(result.scalars().all())


async def get_rating(db: AsyncSession, target_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.target_id == target_id
        )
    )
    avg_rating, count = result.one()
    return {
        "target_id": str(target_id),
        "average_rating": float(avg_rating or 0),
        "review_count": count,
    }
