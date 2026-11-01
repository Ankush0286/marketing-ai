from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Index,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_models import AuditBase
from app.common.enums import ActivitySeverity, ActivityType


class ActivityLog(AuditBase):
    """
    Append-only unified audit record capturing domain events across accounts,
    campaigns, triggers, outreach, and AI copilot executions.
    """

    __tablename__ = "activity_logs"

    activity_type: Mapped[ActivityType] = mapped_column(
        SAEnum(ActivityType, native_enum=False),
        nullable=False,
        index=True,
    )
    severity: Mapped[ActivitySeverity] = mapped_column(
        SAEnum(ActivitySeverity, native_enum=False),
        default=ActivitySeverity.INFO,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Entity Association (Polymorphic target reference)
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        index=True,
    )

    # Actor responsible (e.g., 'user', 'system_worker', 'agent_copilot')
    actor: Mapped[str] = mapped_column(
        String(50),
        default="system",
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Highly optimized indexes for rendering the dashboard timeline view:
    __table_args__ = (
        Index("ix_activity_logs_created_severity", "created_at", "severity"),
        Index("ix_activity_logs_entity", "entity_type", "entity_id"),
    )
