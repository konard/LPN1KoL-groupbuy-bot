from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import settings
from .models import Base, Clinic


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create database tables and seed demo clinics."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count(Clinic.id)))
        if count == 0:
            session.add_all(
                [
                    Clinic(name="Central Clinic", address="1 Health Avenue"),
                    Clinic(name="Family Care", address="24 Wellness Street"),
                    Clinic(name="Downtown Diagnostics", address="8 Lab Square"),
                ]
            )
            await session.commit()
