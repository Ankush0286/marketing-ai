from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.common.enums import CampaignStatus, PostContentType, PostStatus


@dataclass(frozen=True)
class CreateCampaignCommand:
    """Payload to create a new marketing campaign."""

    name: str
    description: str | None = None
    target_audience: str | None = None
    status: CampaignStatus = CampaignStatus.DRAFT
    start_date: datetime | None = None
    end_date: datetime | None = None
    tags: list[str] = field(default_factory=list)
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateCampaignCommand:
    """Payload to update an existing campaign."""

    campaign_id: UUID
    name: str | None = None
    description: str | None = None
    target_audience: str | None = None
    status: CampaignStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    tags: list[str] | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueuePostCommand:
    """Payload to stage or schedule an outbound post."""

    campaign_id: UUID
    account_id: UUID
    content: str
    content_type: PostContentType = PostContentType.TEXT
    media_urls: list[str] = field(default_factory=list)
    scheduled_at: datetime | None = None
    status: PostStatus = PostStatus.SCHEDULED
    max_retries: int = 3
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdatePostCommand:
    """Payload to edit a pending or draft post before dispatch."""

    post_id: UUID
    account_id: UUID | None = None
    content: str | None = None
    content_type: PostContentType | None = None
    media_urls: list[str] | None = None
    scheduled_at: datetime | None = None
    status: PostStatus | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecordPostDeliveryCommand:
    """Payload emitted by platform adapters upon successful publishing."""

    post_id: UUID
    platform_post_id: str
    platform_post_url: str | None = None


@dataclass(frozen=True)
class RecordPostFailureCommand:
    """Payload emitted by platform adapters or workers when delivery fails."""

    post_id: UUID
    error_message: str
