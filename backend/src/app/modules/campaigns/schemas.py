from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.enums import CampaignStatus, PostContentType, PostStatus
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
    UpdateCampaignCommand,
    UpdatePostCommand,
)

# =============================================================================
# Ingress / Request Schemas (HTTP Inbound)
# =============================================================================


class CampaignCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/campaigns/"""

    name: str = Field(..., min_length=1, max_length=150, examples=["Q4 AI Tool Launch"])
    description: str | None = Field(None, max_length=2000)
    target_audience: str | None = Field(None, max_length=255, examples=["Tech Founders, Solo Hackers"])
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT)
    start_date: datetime | None = None
    end_date: datetime | None = None
    tags: list[str] = Field(default_factory=list, examples=[["saas", "growth", "launch"]])
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_date_boundaries(self) -> "CampaignCreateRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self

    def to_command(self) -> CreateCampaignCommand:
        return CreateCampaignCommand(**self.model_dump())


class CampaignUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/campaigns/{campaign_id}"""

    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    target_audience: str | None = Field(None, max_length=255)
    status: CampaignStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    tags: list[str] | None = None
    extra_metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_date_boundaries(self) -> "CampaignUpdateRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self

    def to_command(self, campaign_id: UUID) -> UpdateCampaignCommand:
        return UpdateCampaignCommand(
            campaign_id=campaign_id,
            **self.model_dump(exclude_unset=True),
        )


class PostQueueRequest(BaseModel):
    """Payload accepted by POST /api/v1/campaigns/{campaign_id}/posts/"""

    account_id: UUID = Field(..., description="Target ConnectedAccount ID")
    content: str = Field(..., min_length=1, max_length=10000, description="Post text or thread copy")
    content_type: PostContentType = Field(default=PostContentType.TEXT)
    media_urls: list[str] = Field(default_factory=list, max_length=10)
    scheduled_at: datetime | None = Field(
        None,
        description="Target publish timestamp (must be in the future if status is 'scheduled')",
    )
    status: PostStatus = Field(default=PostStatus.SCHEDULED)
    max_retries: int = Field(default=3, ge=0, le=10)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scheduling_rules(self) -> "PostQueueRequest":
        if self.status == PostStatus.SCHEDULED:
            if not self.scheduled_at:
                raise ValueError("scheduled_at is required when status is 'scheduled'")
            scheduled = (
                self.scheduled_at.replace(tzinfo=UTC)
                if self.scheduled_at.tzinfo is None
                else self.scheduled_at
            )
            if scheduled <= datetime.now(UTC):
                raise ValueError("scheduled_at must be set to a future timestamp")
        return self

    def to_command(self, campaign_id: UUID) -> QueuePostCommand:
        return QueuePostCommand(
            campaign_id=campaign_id,
            **self.model_dump(),
        )


class PostUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/campaigns/posts/{post_id}"""

    account_id: UUID | None = None
    content: str | None = Field(None, min_length=1, max_length=10000)
    content_type: PostContentType | None = None
    media_urls: list[str] | None = Field(None, max_length=10)
    scheduled_at: datetime | None = None
    status: PostStatus | None = None
    extra_metadata: dict[str, Any] | None = None

    def to_command(self, post_id: UUID) -> UpdatePostCommand:
        return UpdatePostCommand(
            post_id=post_id,
            **self.model_dump(exclude_unset=True),
        )


# =============================================================================
# Egress / Response Schemas (HTTP Outbound)
# =============================================================================


class PostResponse(BaseModel):
    """Sanitized public view of a scheduled post."""

    id: UUID
    campaign_id: UUID
    account_id: UUID
    content: str
    content_type: PostContentType
    media_urls: list[str]
    status: PostStatus
    scheduled_at: datetime | None
    published_at: datetime | None
    platform_post_id: str | None = None
    platform_post_url: str | None = None
    last_error_message: str | None = None
    retry_count: int
    max_retries: int
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignResponse(BaseModel):
    """Sanitized summary view of a campaign."""

    id: UUID
    name: str
    description: str | None = None
    target_audience: str | None = None
    status: CampaignStatus
    start_date: datetime | None = None
    end_date: datetime | None = None
    tags: list[str]
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignDetailResponse(CampaignResponse):
    """Detailed campaign response with nested post list."""

    posts: list[PostResponse] = Field(default_factory=list)
