from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.common.enums import ActivitySeverity, ActivityType


@dataclass(frozen=True)
class LogActivityCommand:
    """Payload to record an append-only event in the audit trail."""

    activity_type: ActivityType
    title: str
    severity: ActivitySeverity = ActivitySeverity.INFO
    description: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor: str = "system"
    extra_metadata: dict[str, Any] = field(default_factory=dict)
