from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutreachMessage(Base):

    __tablename__ = "outreach_messages"

    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "influencer_id",
            "channel",
            name="uq_campaign_influencer_channel"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    influencer_id: Mapped[int] = mapped_column(
        ForeignKey("influencers.id"),
        nullable=False
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id"),
        nullable=False
    )

    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    subject: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )