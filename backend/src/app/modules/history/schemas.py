from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import ActivitySeverity, ActivityType
from app.modules.history.commands import LogActivityCommand

# =============================================================================
# Ingress / Request Schemas (HTTP Inbound)
# =============================================================================


class ActivityLogCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/history/"""

    activity_type: ActivityType
    title: str = Field(..., min_length=1, max_length=200, examples=["Campaign Created"])
    severity: ActivitySeverity = Field(default=ActivitySeverity.INFO)
    description: str | None = Field(None, max_length=5000)
    entity_type: str | None = Field(None, max_length=50, examples=["campaign"])
    entity_id: UUID | None = None
    actor: str = Field(default="user", max_length=50, examples=["user", "agent_copilot"])
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self) -> LogActivityCommand:
        return LogActivityCommand(**self.model_dump())


# =============================================================================
# Egress / Response Schemas (HTTP Outbound)
# =============================================================================


class ActivityLogResponse(BaseModel):
    """Public view of an audit log entry."""

    id: UUID
    activity_type: ActivityType
    severity: ActivitySeverity
    title: str
    description: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor: str
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
