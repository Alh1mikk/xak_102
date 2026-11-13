
import uuid
from datetime import datetime

from sqlalchemy import (
    String, Text, Integer, DateTime, ForeignKey,
    CheckConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        CheckConstraint(
            "price_min IS NULL OR price_min >= 0",
            name="check_event_price_min",
        ),
        CheckConstraint(
            "price_max IS NULL OR price_max >= 0",
            name="check_event_price_max",
        ),
        CheckConstraint(
            "price_min IS NULL OR price_max IS NULL OR price_max >= price_min",
            name="check_event_price_range",
        ),
        CheckConstraint(
            "age_limit IS NULL OR age_limit >= 0",
            name="check_event_age_limit",
        ),
        CheckConstraint(
            "end_at IS NULL OR end_at >= start_at",
            name="check_event_dates",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'cancelled')",
            name="check_event_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=True
    )

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    organizer: Mapped[str | None] = mapped_column(String(300), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
