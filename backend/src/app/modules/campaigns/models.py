from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_models import AuditBase
from app.common.enums import CampaignStatus, PostContentType, PostStatus
from app.modules.accounts.models import ConnectedAccount


class Campaign(AuditBase):
    """
    Groups related marketing objectives, audiences, and multi-channel scheduled posts.
    """

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    target_audience: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, native_enum=False),
        default=CampaignStatus.DRAFT,
        nullable=False,
        index=True,
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 1:N Relationship with posts (deleting a campaign deletes its scheduled posts)
    posts: Mapped[list["ScheduledPost"]] = relationship(
        "ScheduledPost",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="ScheduledPost.created_at",
    )

    def is_active(self) -> bool:
        """Determines if the campaign is currently running and accepting schedules."""
        if self.status != CampaignStatus.ACTIVE:
            return False
        now = datetime.now(UTC)
        if self.start_date and now < self.start_date:
            return False
        return not (self.end_date and now > self.end_date)


class ScheduledPost(AuditBase):
    """
    An individual content item queued for dispatch to a specific ConnectedAccount.
    """

    __tablename__ = "scheduled_posts"

    # --------------- Foreign Key Associations ---------------
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------- Content & Media Specifications ---------------
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_type: Mapped[PostContentType] = mapped_column(
        SAEnum(PostContentType, native_enum=False),
        default=PostContentType.TEXT,
        nullable=False,
    )
    # Relative paths within storage/media/ or external hosted CDN URLs
    media_urls: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # --------------- Scheduling & Status Lifecycle ---------------
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(PostStatus, native_enum=False),
        default=PostStatus.DRAFT,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------- Delivery Diagnostics & Retries ---------------
    platform_post_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    platform_post_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # --------------- ORM Relationships ---------------
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="posts",
    )
    # Eagerly joins the account to eliminate N+1 queries when workers poll posts
    account: Mapped[ConnectedAccount] = relationship(
        "ConnectedAccount",
        lazy="joined",
    )

    # Optimized index for the background post dispatcher query:
    # SELECT * FROM scheduled_posts WHERE status = 'scheduled' AND scheduled_at <= :now
    __table_args__ = (
        Index("ix_scheduled_posts_status_scheduled_at", "status", "scheduled_at"),
    )

    # --------------- State Transition Helpers ---------------
    def is_due(self) -> bool:
        """Checks if post is currently waiting and reached its scheduled time."""
        if self.status != PostStatus.SCHEDULED or not self.scheduled_at:
            return False
        scheduled = (
            self.scheduled_at.replace(tzinfo=UTC)
            if self.scheduled_at.tzinfo is None
            else self.scheduled_at
        )
        return datetime.now(UTC) >= scheduled

    def can_retry(self) -> bool:
        """Determines if a failed post has retry attempts remaining."""
        return self.retry_count < self.max_retries

    def mark_as_publishing(self) -> None:
        """Transitions post into the active delivery phase."""
        self.status = PostStatus.PUBLISHING
        self.last_error_message = None

    def mark_as_published(self, post_id: str, post_url: str | None = None) -> None:
        """Finalizes post upon confirmed receipt from the social platform."""
        self.status = PostStatus.PUBLISHED
        self.platform_post_id = post_id
        self.platform_post_url = post_url
        self.published_at = datetime.now(UTC)
        self.last_error_message = None

    def mark_as_failed(self, error: str) -> None:
        """Records failure reason and increments retry tally."""
        self.retry_count += 1
        self.last_error_message = error
        if self.can_retry():
            self.status = PostStatus.SCHEDULED  # Ready for worker retry
        else:
            self.status = PostStatus.FAILED
