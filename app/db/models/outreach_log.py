from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutreachLog(Base):

    __tablename__ = "outreach_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey("outreach_messages.id"),
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )