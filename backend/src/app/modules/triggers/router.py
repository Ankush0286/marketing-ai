from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.enums import PlatformType, TriggerMatchStatus
from app.db.dependencies import get_db_session
from app.modules.triggers.schemas import (
    TriggerMatchResponse,
    TriggerMatchReviewRequest,
    TriggerRuleCreateRequest,
    TriggerRuleResponse,
    TriggerRuleUpdateRequest,
    WatchedHandleCreateRequest,
    WatchedHandleResponse,
    WatchedHandleUpdateRequest,
)
from app.modules.triggers.service import TriggerService

router = APIRouter()


def get_trigger_service(db: Session = Depends(get_db_session)) -> TriggerService:
    """Dependency injection factory for TriggerService."""
    return TriggerService(db)


# =============================================================================
# Watched Handles Endpoints
# =============================================================================


@router.post(
    "/handles",
    response_model=WatchedHandleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new target account or competitor to monitor",
)
def add_watched_handle(
    payload: WatchedHandleCreateRequest,
    service: TriggerService = Depends(get_trigger_service),
) -> WatchedHandleResponse:
    handle = service.add_watched_handle(payload.to_command())
    return WatchedHandleResponse.model_validate(handle)


@router.get(
    "/handles",
    response_model=list[WatchedHandleResponse],
    status_code=status.HTTP_200_OK,
    summary="List all monitored competitor accounts",
)
def list_watched_handles(
    active_only: bool = Query(default=False, description="Filter for active handles only"),
    service: TriggerService = Depends(get_trigger_service),
) -> list[WatchedHandleResponse]:
    handles = service.list_watched_handles(active_only=active_only)
    return [WatchedHandleResponse.model_validate(h) for h in handles]


@router.get(
    "/handles/{handle_id}",
    response_model=WatchedHandleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a watched handle by ID",
)
def get_watched_handle(
    handle_id: UUID,
    service: TriggerService = Depends(get_trigger_service),
) -> WatchedHandleResponse:
    handle = service.get_watched_handle_by_id_or_raise(handle_id)
    return WatchedHandleResponse.model_validate(handle)


@router.patch(
    "/handles/{handle_id}",
    response_model=WatchedHandleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update scraping frequency or status of a watched handle",
)
def update_watched_handle(
    handle_id: UUID,
    payload: WatchedHandleUpdateRequest,
    service: TriggerService = Depends(get_trigger_service),
) -> WatchedHandleResponse:
    handle = service.update_watched_handle(payload.to_command(handle_id))
    return WatchedHandleResponse.model_validate(handle)


@router.delete(
    "/handles/{handle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop monitoring and delete a watched handle",
)
def delete_watched_handle(
    handle_id: UUID,
    service: TriggerService = Depends(get_trigger_service),
) -> None:
    service.delete_watched_handle(handle_id)


# =============================================================================
# Trigger Rules Endpoints
# =============================================================================


@router.post(
    "/rules",
    response_model=TriggerRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new keyword monitoring & auto-reply rule",
)
def create_trigger_rule(
    payload: TriggerRuleCreateRequest,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerRuleResponse:
    rule = service.create_rule(payload.to_command())
    return TriggerRuleResponse.model_validate(rule)


@router.get(
    "/rules",
    response_model=list[TriggerRuleResponse],
    status_code=status.HTTP_200_OK,
    summary="List all keyword trigger rules",
)
def list_trigger_rules(
    platform: PlatformType | None = Query(default=None, description="Filter rules by platform"),
    active_only: bool = Query(default=False, description="Filter for active rules only"),
    service: TriggerService = Depends(get_trigger_service),
) -> list[TriggerRuleResponse]:
    rules = service.list_rules(platform=platform, active_only=active_only)
    return [TriggerRuleResponse.model_validate(r) for r in rules]


@router.get(
    "/rules/{rule_id}",
    response_model=TriggerRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a trigger rule by ID",
)
def get_trigger_rule(
    rule_id: UUID,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerRuleResponse:
    rule = service.get_rule_by_id_or_raise(rule_id)
    return TriggerRuleResponse.model_validate(rule)


@router.patch(
    "/rules/{rule_id}",
    response_model=TriggerRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update trigger keywords, templates, or cooldown settings",
)
def update_trigger_rule(
    rule_id: UUID,
    payload: TriggerRuleUpdateRequest,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerRuleResponse:
    rule = service.update_rule(payload.to_command(rule_id))
    return TriggerRuleResponse.model_validate(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trigger rule",
)
def delete_trigger_rule(
    rule_id: UUID,
    service: TriggerService = Depends(get_trigger_service),
) -> None:
    service.delete_rule(rule_id)


# =============================================================================
# Trigger Matches Endpoints
# =============================================================================


@router.get(
    "/matches",
    response_model=list[TriggerMatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List intercepted keyword matches and auto-reply opportunities",
)
def list_trigger_matches(
    rule_id: UUID | None = Query(default=None, description="Filter matches by rule ID"),
    status: TriggerMatchStatus | None = Query(default=None, description="Filter by match status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max matches to return"),
    service: TriggerService = Depends(get_trigger_service),
) -> list[TriggerMatchResponse]:
    matches = service.list_matches(rule_id=rule_id, status=status, limit=limit)
    return [TriggerMatchResponse.model_validate(m) for m in matches]


@router.get(
    "/matches/{match_id}",
    response_model=TriggerMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a trigger match by ID",
)
def get_trigger_match(
    match_id: UUID,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerMatchResponse:
    match = service.get_match_by_id_or_raise(match_id)
    return TriggerMatchResponse.model_validate(match)


@router.post(
    "/matches/{match_id}/review",
    response_model=TriggerMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or ignore an auto-reply match",
)
def review_trigger_match(
    match_id: UUID,
    payload: TriggerMatchReviewRequest,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerMatchResponse:
    match = service.review_match(payload.to_command(match_id))
    return TriggerMatchResponse.model_validate(match)
