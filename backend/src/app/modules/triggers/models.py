from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_models import AuditBase
from app.common.enums import PlatformType, TriggerActionType, TriggerMatchStatus
from app.modules.accounts.models import ConnectedAccount


class WatchedHandle(AuditBase):
    """
    Target profile or competitor account being monitored by the scraper worker.
    """

    __tablename__ = "watched_handles"

    platform: Mapped[PlatformType] = mapped_column(
        SAEnum(PlatformType, native_enum=False),
        nullable=False,
        index=True,
    )
    handle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    scrape_frequency_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    rules: Mapped[list["TriggerRule"]] = relationship(
        "TriggerRule",
        back_populates="watched_handle",
        cascade="all, delete-orphan",
    )
    matches: Mapped[list["TriggerMatch"]] = relationship(
        "TriggerMatch",
        back_populates="watched_handle",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("platform", "handle", name="uq_watched_handles_platform_handle"),
    )


class TriggerRule(AuditBase):
    """
    Evaluation rule specifying keyword matches, negative keywords, cooldowns,
    and the connected account used for automated replies.
    """

    __tablename__ = "trigger_rules"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    platform: Mapped[PlatformType] = mapped_column(
        SAEnum(PlatformType, native_enum=False),
        nullable=False,
        index=True,
    )

    # Optional: Associate rule with a specific competitor or keep None for global monitoring
    watched_handle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("watched_handles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # The social profile that executes the auto-reply or sends the outreach
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action_type: Mapped[TriggerActionType] = mapped_column(
        SAEnum(TriggerActionType, native_enum=False),
        default=TriggerActionType.STAGE_DRAFT,
        nullable=False,
    )

    # Filtering Criteria (case-insensitive string arrays)
    keywords_any: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    keywords_all: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    keywords_exclude: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    response_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    watched_handle: Mapped[WatchedHandle | None] = relationship(
        "WatchedHandle",
        back_populates="rules",
    )
    account: Mapped[ConnectedAccount] = relationship(
        "ConnectedAccount",
        lazy="joined",
    )
    matches: Mapped[list["TriggerMatch"]] = relationship(
        "TriggerMatch",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class TriggerMatch(AuditBase):
    """
    An intercepted post or tweet that matched a TriggerRule, tracking the
    approval status and dispatch diagnostics.
    """

    __tablename__ = "trigger_matches"

    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("trigger_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    watched_handle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("watched_handles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Scraped Source Context
    platform_post_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    platform_post_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    author_handle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    post_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    matched_keywords: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Resolution & Auto-Reply Dispatch State
    status: Mapped[TriggerMatchStatus] = mapped_column(
        SAEnum(TriggerMatchStatus, native_enum=False),
        default=TriggerMatchStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
    )
    generated_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    published_reply_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    rule: Mapped[TriggerRule] = relationship(
        "TriggerRule",
        back_populates="matches",
    )
    watched_handle: Mapped[WatchedHandle | None] = relationship(
        "WatchedHandle",
        back_populates="matches",
    )

    __table_args__ = (
        Index("ix_trigger_matches_status_created", "status", "created_at"),
        # Deduplication guarantee: one post cannot match the same rule multiple times
        UniqueConstraint("rule_id", "platform_post_id", name="uq_trigger_matches_rule_post"),
    )

    def mark_as_approved(self, response_text: str | None = None) -> None:
        """Approves match for automated dispatch."""
        self.status = TriggerMatchStatus.APPROVED
        self.reviewed_at = datetime.now(UTC)
        if response_text:
            self.generated_response = response_text

    def mark_as_ignored(self) -> None:
        """Dismisses the match."""
        self.status = TriggerMatchStatus.IGNORED
        self.reviewed_at = datetime.now(UTC)

    def mark_as_dispatched(self, reply_post_id: str) -> None:
        """Records successful dispatch of auto-reply."""
        self.status = TriggerMatchStatus.DISPATCHED
        self.published_reply_id = reply_post_id
        self.dispatched_at = datetime.now(UTC)
        self.last_error_message = None

    def mark_as_failed(self, error: str) -> None:
        """Records auto-reply dispatch failure."""
        self.status = TriggerMatchStatus.FAILED
        self.last_error_message = error
