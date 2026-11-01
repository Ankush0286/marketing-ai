from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachChannel,
    OutreachMessageStatus,
    PlatformType,
)
from app.modules.outreach.commands import (
    CreateLeadCommand,
    CreateOutreachCampaignCommand,
    ReviewMessageCommand,
    StageMessageCommand,
    UpdateLeadCommand,
    UpdateOutreachCampaignCommand,
)

# =============================================================================
# Ingress / Request Schemas (HTTP Inbound)
# =============================================================================


class LeadCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/outreach/leads"""

    platform: PlatformType
    handle: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^@?[A-Za-z0-9_.]+$",
        examples=["@growth_influencer", "indie_founder"],
    )
    display_name: str | None = Field(None, max_length=150)
    bio: str | None = Field(None, max_length=2000)
    profile_url: str | None = Field(None, max_length=500)
    email: EmailStr | None = None
    follower_count: int | None = Field(None, ge=0)
    tier: LeadTier = Field(default=LeadTier.NANO)
    stage: LeadStage = Field(default=LeadStage.DISCOVERED)
    tags: list[str] = Field(default_factory=list, examples=[["saas", "creator"]])
    notes: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self) -> CreateLeadCommand:
        return CreateLeadCommand(
            platform=self.platform,
            handle=self.handle.lstrip("@").strip(),
            display_name=self.display_name,
            bio=self.bio,
            profile_url=self.profile_url,
            email=str(self.email) if self.email else None,
            follower_count=self.follower_count,
            tier=self.tier,
            stage=self.stage,
            tags=self.tags,
            notes=self.notes,
            extra_metadata=self.extra_metadata,
        )


class LeadUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/outreach/leads/{lead_id}"""

    display_name: str | None = Field(None, max_length=150)
    bio: str | None = Field(None, max_length=2000)
    profile_url: str | None = Field(None, max_length=500)
    email: EmailStr | None = None
    follower_count: int | None = Field(None, ge=0)
    tier: LeadTier | None = None
    stage: LeadStage | None = None
    tags: list[str] | None = None
    notes: str | None = None
    extra_metadata: dict[str, Any] | None = None

    def to_command(self, lead_id: UUID) -> UpdateLeadCommand:
        data = self.model_dump(exclude_unset=True)
        if "email" in data and data["email"] is not None:
            data["email"] = str(data["email"])
        return UpdateLeadCommand(lead_id=lead_id, **data)


class OutreachCampaignCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/outreach/campaigns"""

    name: str = Field(..., min_length=1, max_length=150, examples=["Micro-Influencer Q4 Outreach"])
    account_id: UUID = Field(..., description="ConnectedAccount used to send cold DMs")
    description: str | None = Field(None, max_length=2000)
    is_active: bool = Field(default=True)
    target_criteria: dict[str, Any] = Field(default_factory=dict)
    template: str | None = Field(
        None,
        description="Cold DM template with {handle} and {display_name} placeholders",
        examples=["Hey @{handle}, love your insights on {topic}!"],
    )
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self) -> CreateOutreachCampaignCommand:
        return CreateOutreachCampaignCommand(**self.model_dump())


class OutreachCampaignUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/outreach/campaigns/{campaign_id}"""

    name: str | None = Field(None, min_length=1, max_length=150)
    account_id: UUID | None = None
    description: str | None = Field(None, max_length=2000)
    is_active: bool | None = None
    target_criteria: dict[str, Any] | None = None
    template: str | None = None
    extra_metadata: dict[str, Any] | None = None

    def to_command(self, campaign_id: UUID) -> UpdateOutreachCampaignCommand:
        return UpdateOutreachCampaignCommand(
            campaign_id=campaign_id,
            **self.model_dump(exclude_unset=True),
        )


class MessageStageRequest(BaseModel):
    """Payload accepted by POST /api/v1/outreach/messages/stage"""

    lead_id: UUID
    account_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)
    outreach_campaign_id: UUID | None = None
    channel: OutreachChannel = Field(default=OutreachChannel.DM)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self) -> StageMessageCommand:
        return StageMessageCommand(**self.model_dump())


class MessageReviewRequest(BaseModel):
    """Payload accepted by POST /api/v1/outreach/messages/{message_id}/review"""

    status: OutreachMessageStatus = Field(
        ...,
        description="Must be 'approved' or 'rejected'",
    )
    edited_content: str | None = Field(
        None,
        max_length=5000,
        description="Refined message copy replacing the staged draft",
    )
    rejection_reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_review_action(self) -> "MessageReviewRequest":
        if self.status not in (OutreachMessageStatus.APPROVED, OutreachMessageStatus.REJECTED):
            raise ValueError("Review status must be either 'approved' or 'rejected'")
        return self

    def to_command(self, message_id: UUID) -> ReviewMessageCommand:
        return ReviewMessageCommand(
            message_id=message_id,
            status=self.status,
            edited_content=self.edited_content,
            rejection_reason=self.rejection_reason,
        )


# =============================================================================
# Egress / Response Schemas (HTTP Outbound)
# =============================================================================


class LeadResponse(BaseModel):
    """Public view of a CRM lead."""

    id: UUID
    platform: PlatformType
    handle: str
    display_name: str | None = None
    bio: str | None = None
    profile_url: str | None = None
    email: str | None = None
    follower_count: int | None = None
    tier: LeadTier
    stage: LeadStage
    tags: list[str]
    notes: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutreachCampaignResponse(BaseModel):
    """Public view of an outreach campaign."""

    id: UUID
    name: str
    account_id: UUID
    description: str | None = None
    is_active: bool
    target_criteria: dict[str, Any]
    template: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutreachMessageResponse(BaseModel):
    """Public view of a staged or dispatched cold message."""

    id: UUID
    outreach_campaign_id: UUID | None = None
    lead_id: UUID
    account_id: UUID
    channel: OutreachChannel
    content: str
    status: OutreachMessageStatus
    reviewed_at: datetime | None = None
    sent_at: datetime | None = None
    platform_message_id: str | None = None
    last_error_message: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
