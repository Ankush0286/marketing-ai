from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.common.enums import ActivitySeverity, ActivityType
from app.modules.history.commands import LogActivityCommand
from app.modules.history.exceptions import ActivityLogNotFoundError
from app.modules.history.models import ActivityLog


def _ensure_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class HistoryService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_by_id(self, log_id: UUID | str) -> ActivityLog | None:
        """Fetch a single audit log entry by UUID, returning None if not found."""
        target_id = _ensure_uuid(log_id)
        return (
            self.db.query(ActivityLog)
            .filter(ActivityLog.id == target_id)
            .first()
        )

    def get_by_id_or_raise(self, log_id: UUID | str) -> ActivityLog:
        """Fetch a single audit log entry or raise ActivityLogNotFoundError."""
        log = self.get_by_id(log_id)
        if not log:
            raise ActivityLogNotFoundError(log_id)
        return log

    def list_activities(
        self,
        activity_type: ActivityType | None = None,
        severity: ActivitySeverity | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityLog]:
        """
        Query the audit trail with multi-parameter filtering and pagination.
        Ordered by newest events first.
        """
        query = self.db.query(ActivityLog).order_by(ActivityLog.created_at.desc())

        if activity_type is not None:
            query = query.filter(ActivityLog.activity_type == activity_type)
        if severity is not None:
            query = query.filter(ActivityLog.severity == severity)
        if entity_type is not None:
            query = query.filter(ActivityLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.filter(ActivityLog.entity_id == entity_id)

        if since is not None:
            since_utc = since.replace(tzinfo=UTC) if since.tzinfo is None else since
            query = query.filter(ActivityLog.created_at >= since_utc)

        if until is not None:
            until_utc = until.replace(tzinfo=UTC) if until.tzinfo is None else until
            query = query.filter(ActivityLog.created_at <= until_utc)

        return query.offset(offset).limit(limit).all()

    def count_activities(
        self,
        activity_type: ActivityType | None = None,
        severity: ActivitySeverity | None = None,
    ) -> int:
        """Count total matching activities for dashboard metrics."""
        query = self.db.query(ActivityLog)
        if activity_type is not None:
            query = query.filter(ActivityLog.activity_type == activity_type)
        if severity is not None:
            query = query.filter(ActivityLog.severity == severity)
        return query.count()

    # =========================================================================
    # Mutation Methods
    # =========================================================================

    def log_activity(self, cmd: LogActivityCommand) -> ActivityLog:
        """Appends a new immutable event to the audit trail."""
        log = ActivityLog(
            activity_type=cmd.activity_type,
            title=cmd.title,
            severity=cmd.severity,
            description=cmd.description,
            entity_type=cmd.entity_type,
            entity_id=cmd.entity_id,
            actor=cmd.actor,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def purge_logs_older_than(self, days: int = 90) -> int:
        """
        Data retention policy maintenance helper.
        Purges historical logs older than the specified threshold.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        deleted_count = (
            self.db.query(ActivityLog)
            .filter(ActivityLog.created_at < cutoff)
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted_count
