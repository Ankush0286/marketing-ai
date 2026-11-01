from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.common.enums import PlatformType, TriggerActionType, TriggerMatchStatus


@dataclass(frozen=True)
class AddWatchedHandleCommand:
    """Payload to add a competitor or target account to monitor."""

    platform: PlatformType
    handle: str
    display_name: str | None = None
    scrape_frequency_minutes: int = 30
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateWatchedHandleCommand:
    """Payload to update target account monitoring parameters."""

    handle_id: UUID
    display_name: str | None = None
    is_active: bool | None = None
    scrape_frequency_minutes: int | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CreateTriggerRuleCommand:
    """Payload to create keyword matching and auto-reply rules."""

    name: str
    platform: PlatformType
    account_id: UUID
    description: str | None = None
    watched_handle_id: UUID | None = None
    action_type: TriggerActionType = TriggerActionType.STAGE_DRAFT
    keywords_any: list[str] = field(default_factory=list)
    keywords_all: list[str] = field(default_factory=list)
    keywords_exclude: list[str] = field(default_factory=list)
    response_template: str | None = None
    cooldown_minutes: int = 60
    is_active: bool = True
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateTriggerRuleCommand:
    """Payload to modify keyword rules, response copy, or status."""

    rule_id: UUID
    name: str | None = None
    account_id: UUID | None = None
    description: str | None = None
    watched_handle_id: UUID | None = None
    action_type: TriggerActionType | None = None
    keywords_any: list[str] | None = None
    keywords_all: list[str] | None = None
    keywords_exclude: list[str] | None = None
    response_template: str | None = None
    cooldown_minutes: int | None = None
    is_active: bool | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class EvaluateIncomingPostCommand:
    """Payload representing a fresh post scraped from a competitor feed."""

    platform: PlatformType
    platform_post_id: str
    author_handle: str
    post_content: str
    platform_post_url: str | None = None
    watched_handle_id: UUID | None = None


@dataclass(frozen=True)
class ReviewMatchCommand:
    """Payload to approve, edit, or dismiss a detected opportunity."""

    match_id: UUID
    status: TriggerMatchStatus
    edited_response: str | None = None
