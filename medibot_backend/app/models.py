from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(240), nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="clinic")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    appointment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="scheduled", nullable=False)
    calendar_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    clinic: Mapped[Clinic] = relationship(back_populates="appointments")
