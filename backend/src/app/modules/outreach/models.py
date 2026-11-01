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
from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachChannel,
    OutreachMessageStatus,
    PlatformType,
)
from app.modules.accounts.models import ConnectedAccount


class Lead(AuditBase):
    """
    An influencer, prospect, or competitor lead tracked in the social CRM.
    """

    __tablename__ = "leads"

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
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    profile_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    follower_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    tier: Mapped[LeadTier] = mapped_column(
        SAEnum(LeadTier, native_enum=False),
        default=LeadTier.NANO,
        nullable=False,
    )
    stage: Mapped[LeadStage] = mapped_column(
        SAEnum(LeadStage, native_enum=False),
        default=LeadStage.DISCOVERED,
        nullable=False,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("platform", "handle", name="uq_leads_platform_handle"),
    )

    def can_contact(self) -> bool:
        """Verifies if the lead is in a stage that permits outbound outreach."""
        return self.stage not in (LeadStage.DO_NOT_CONTACT, LeadStage.CONVERTED)


class OutreachCampaign(AuditBase):
    """
    A segmented cold messaging initiative targeting specific leads.
    """

    __tablename__ = "outreach_campaigns"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # The default account used to dispatch DMs for this campaign
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    target_criteria: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    account: Mapped[ConnectedAccount] = relationship(
        "ConnectedAccount",
        lazy="joined",
    )
    messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class OutreachMessage(AuditBase):
    """
    A cold DM or email staged for human-in-the-loop review and automated dispatch.
    """

    __tablename__ = "outreach_messages"

    outreach_campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("outreach_campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel: Mapped[OutreachChannel] = mapped_column(
        SAEnum(OutreachChannel, native_enum=False),
        default=OutreachChannel.DM,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[OutreachMessageStatus] = mapped_column(
        SAEnum(OutreachMessageStatus, native_enum=False),
        default=OutreachMessageStatus.STAGED,
        nullable=False,
        index=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    platform_message_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    campaign: Mapped[OutreachCampaign | None] = relationship(
        "OutreachCampaign",
        back_populates="messages",
    )
    lead: Mapped[Lead] = relationship(
        "Lead",
        back_populates="messages",
        lazy="joined",
    )
    account: Mapped[ConnectedAccount] = relationship(
        "ConnectedAccount",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_outreach_messages_status_created", "status", "created_at"),
    )

    def mark_as_approved(self, edited_content: str | None = None) -> None:
        """Approves staged message for worker dispatch."""
        self.status = OutreachMessageStatus.APPROVED
        self.reviewed_at = datetime.now(UTC)
        if edited_content:
            self.content = edited_content

    def mark_as_rejected(self, reason: str | None = None) -> None:
        """Rejects staged message."""
        self.status = OutreachMessageStatus.REJECTED
        self.reviewed_at = datetime.now(UTC)
        if reason:
            self.last_error_message = reason

    def mark_as_dispatched(self, platform_id: str) -> None:
        """Finalizes message upon platform delivery and advances lead stage."""
        self.status = OutreachMessageStatus.DISPATCHED
        self.platform_message_id = platform_id
        self.sent_at = datetime.now(UTC)
        self.last_error_message = None

    def mark_as_failed(self, error: str) -> None:
        """Records delivery error."""
        self.status = OutreachMessageStatus.FAILED
        self.last_error_message = error
