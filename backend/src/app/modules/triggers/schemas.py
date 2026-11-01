from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.enums import PlatformType, TriggerActionType, TriggerMatchStatus
from app.modules.triggers.commands import (
    AddWatchedHandleCommand,
    CreateTriggerRuleCommand,
    ReviewMatchCommand,
    UpdateTriggerRuleCommand,
    UpdateWatchedHandleCommand,
)

# =============================================================================
# Ingress / Request Schemas (HTTP Inbound)
# =============================================================================


class WatchedHandleCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/triggers/handles/"""

    platform: PlatformType
    handle: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^@?[A-Za-z0-9_.]+$",
        examples=["@competitor_ceo", "competitor_brand"],
    )
    display_name: str | None = Field(None, max_length=150)
    scrape_frequency_minutes: int = Field(default=30, ge=5, le=1440)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self) -> AddWatchedHandleCommand:
        return AddWatchedHandleCommand(
            platform=self.platform,
            handle=self.handle.lstrip("@").strip(),
            display_name=self.display_name,
            scrape_frequency_minutes=self.scrape_frequency_minutes,
            extra_metadata=self.extra_metadata,
        )


class WatchedHandleUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/triggers/handles/{handle_id}"""

    display_name: str | None = Field(None, max_length=150)
    is_active: bool | None = None
    scrape_frequency_minutes: int | None = Field(None, ge=5, le=1440)
    extra_metadata: dict[str, Any] | None = None

    def to_command(self, handle_id: UUID) -> UpdateWatchedHandleCommand:
        return UpdateWatchedHandleCommand(
            handle_id=handle_id,
            **self.model_dump(exclude_unset=True),
        )


class TriggerRuleCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/triggers/rules/"""

    name: str = Field(..., min_length=1, max_length=150, examples=["Pricing Complaints Auto-Reply"])
    description: str | None = Field(None, max_length=2000)
    platform: PlatformType
    account_id: UUID = Field(..., description="ConnectedAccount used for outbound replies")
    watched_handle_id: UUID | None = Field(None, description="Optional target handle to scope rule")
    action_type: TriggerActionType = Field(default=TriggerActionType.STAGE_DRAFT)

    keywords_any: list[str] = Field(default_factory=list, examples=[["expensive", "pricing", "alternative", "#saas"]])
    keywords_all: list[str] = Field(default_factory=list, examples=[["looking", "tool"]])
    keywords_exclude: list[str] = Field(default_factory=list, examples=[["hiring", "job"]])

    response_template: str | None = Field(
        None,
        description="Response template with {author} placeholder",
        examples=["Hey @{author}, check out our open-source alternative!"],
    )
    cooldown_minutes: int = Field(default=60, ge=1, le=10080)
    is_active: bool = Field(default=True)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_keyword_definitions(self) -> "TriggerRuleCreateRequest":
        has_any = any(k.strip() for k in self.keywords_any)
        has_all = any(k.strip() for k in self.keywords_all)
        if not has_any and not has_all:
            raise ValueError("At least one non-empty keyword in keywords_any or keywords_all must be defined")
        return self

    def to_command(self) -> CreateTriggerRuleCommand:
        return CreateTriggerRuleCommand(**self.model_dump())


class TriggerRuleUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/triggers/rules/{rule_id}"""

    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    account_id: UUID | None = None
    watched_handle_id: UUID | None = None
    action_type: TriggerActionType | None = None
    keywords_any: list[str] | None = None
    keywords_all: list[str] | None = None
    keywords_exclude: list[str] | None = None
    response_template: str | None = None
    cooldown_minutes: int | None = Field(None, ge=1, le=10080)
    is_active: bool | None = None
    extra_metadata: dict[str, Any] | None = None

    def to_command(self, rule_id: UUID) -> UpdateTriggerRuleCommand:
        return UpdateTriggerRuleCommand(
            rule_id=rule_id,
            **self.model_dump(exclude_unset=True),
        )


class TriggerMatchReviewRequest(BaseModel):
    """Payload accepted by POST /api/v1/triggers/matches/{match_id}/review"""

    status: TriggerMatchStatus = Field(
        ...,
        description="Must be 'approved' or 'ignored'",
    )
    edited_response: str | None = Field(
        None,
        max_length=5000,
        description="Optional refined response copy replacing template",
    )

    @model_validator(mode="after")
    def validate_review_state(self) -> "TriggerMatchReviewRequest":
        if self.status not in (TriggerMatchStatus.APPROVED, TriggerMatchStatus.IGNORED):
            raise ValueError("Review status must be either 'approved' or 'ignored'")
        return self

    def to_command(self, match_id: UUID) -> ReviewMatchCommand:
        return ReviewMatchCommand(
            match_id=match_id,
            status=self.status,
            edited_response=self.edited_response,
        )


# =============================================================================
# Egress / Response Schemas (HTTP Outbound)
# =============================================================================


class WatchedHandleResponse(BaseModel):
    """Public view of a monitored profile."""

    id: UUID
    platform: PlatformType
    handle: str
    display_name: str | None = None
    is_active: bool
    scrape_frequency_minutes: int
    last_scraped_at: datetime | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TriggerRuleResponse(BaseModel):
    """Public view of a keyword trigger rule."""

    id: UUID
    name: str
    description: str | None = None
    platform: PlatformType
    account_id: UUID
    watched_handle_id: UUID | None = None
    action_type: TriggerActionType
    keywords_any: list[str]
    keywords_all: list[str]
    keywords_exclude: list[str]
    response_template: str | None = None
    cooldown_minutes: int
    is_active: bool
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TriggerMatchResponse(BaseModel):
    """Public view of an intercepted conversation opportunity."""

    id: UUID
    rule_id: UUID
    watched_handle_id: UUID | None = None
    platform_post_id: str
    platform_post_url: str | None = None
    author_handle: str
    post_content: str
    matched_keywords: list[str]
    status: TriggerMatchStatus
    generated_response: str | None = None
    published_reply_id: str | None = None
    last_error_message: str | None = None
    reviewed_at: datetime | None = None
    dispatched_at: datetime | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
