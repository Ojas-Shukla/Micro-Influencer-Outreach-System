from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Influencer(Base):

    __tablename__ = "influencers"

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "username",
            name="uq_influencer_platform_username"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    platform_user_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    username: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    display_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    profile_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    niche: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    bio: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )

    followers_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    following_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    posts_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    avg_likes: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    avg_comments: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    engagement_rate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )