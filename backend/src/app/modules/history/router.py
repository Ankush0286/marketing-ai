from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.enums import ActivitySeverity, ActivityType
from app.db.dependencies import get_db_session
from app.modules.history.schemas import (
    ActivityLogCreateRequest,
    ActivityLogResponse,
)
from app.modules.history.service import HistoryService

router = APIRouter()


def get_history_service(db: Session = Depends(get_db_session)) -> HistoryService:
    """Dependency injection factory for HistoryService."""
    return HistoryService(db)


@router.post(
    "/",
    response_model=ActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an audit log entry",
)
def record_activity_log(
    payload: ActivityLogCreateRequest,
    service: HistoryService = Depends(get_history_service),
) -> ActivityLogResponse:
    log = service.log_activity(payload.to_command())
    return ActivityLogResponse.model_validate(log)


@router.get(
    "/",
    response_model=list[ActivityLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Query unified activity audit trail",
)
def list_activity_logs(
    activity_type: ActivityType | None = Query(
        default=None, description="Filter by event type (e.g. post_published, lead_imported)"
    ),
    severity: ActivitySeverity | None = Query(
        default=None, description="Filter by severity level (info, success, warning, error)"
    ),
    entity_type: str | None = Query(
        default=None, description="Filter by target entity type (account, campaign, post, lead)"
    ),
    entity_id: UUID | None = Query(
        default=None, description="Filter by specific entity UUID"
    ),
    since: datetime | None = Query(
        default=None, description="Filter events created on or after this timestamp"
    ),
    until: datetime | None = Query(
        default=None, description="Filter events created on or before this timestamp"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    service: HistoryService = Depends(get_history_service),
) -> list[ActivityLogResponse]:
    logs = service.list_activities(
        activity_type=activity_type,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return [ActivityLogResponse.model_validate(log) for log in logs]


@router.get(
    "/{log_id}",
    response_model=ActivityLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an audit log entry by ID",
)
def get_activity_log(
    log_id: UUID,
    service: HistoryService = Depends(get_history_service),
) -> ActivityLogResponse:
    log = service.get_by_id_or_raise(log_id)
    return ActivityLogResponse.model_validate(log)
