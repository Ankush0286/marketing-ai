from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachChannel,
    OutreachMessageStatus,
    PlatformType,
)


@dataclass(frozen=True)
class CreateLeadCommand:
    """Payload to import or create a new lead in the CRM."""

    platform: PlatformType
    handle: str
    display_name: str | None = None
    bio: str | None = None
    profile_url: str | None = None
    email: str | None = None
    follower_count: int | None = None
    tier: LeadTier = LeadTier.NANO
    stage: LeadStage = LeadStage.DISCOVERED
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateLeadCommand:
    """Payload to update lead profile or progression stage."""

    lead_id: UUID
    display_name: str | None = None
    bio: str | None = None
    profile_url: str | None = None
    email: str | None = None
    follower_count: int | None = None
    tier: LeadTier | None = None
    stage: LeadStage | None = None
    tags: list[str] | None = None
    notes: str | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CreateOutreachCampaignCommand:
    """Payload to create a targeted cold outreach campaign."""

    name: str
    account_id: UUID
    description: str | None = None
    is_active: bool = True
    target_criteria: dict[str, Any] = field(default_factory=dict)
    template: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateOutreachCampaignCommand:
    """Payload to update an outreach campaign."""

    campaign_id: UUID
    name: str | None = None
    account_id: UUID | None = None
    description: str | None = None
    is_active: bool | None = None
    target_criteria: dict[str, Any] | None = None
    template: str | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class StageMessageCommand:
    """Payload to stage a cold message behind a human review gate."""

    lead_id: UUID
    account_id: UUID
    content: str
    outreach_campaign_id: UUID | None = None
    channel: OutreachChannel = OutreachChannel.DM
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewMessageCommand:
    """Payload to approve or reject a staged message."""

    message_id: UUID
    status: OutreachMessageStatus
    edited_content: str | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True)
class RecordMessageDeliveryCommand:
    """Payload emitted by platform adapter after sending cold DM."""

    message_id: UUID
    platform_message_id: str


@dataclass(frozen=True)
class RecordMessageFailureCommand:
    """Payload emitted when message delivery fails."""

    message_id: UUID
    error_message: str
