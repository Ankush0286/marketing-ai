from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachMessageStatus,
    PlatformType,
)
from app.db.dependencies import get_db_session
from app.modules.outreach.schemas import (
    LeadCreateRequest,
    LeadResponse,
    LeadUpdateRequest,
    MessageReviewRequest,
    MessageStageRequest,
    OutreachCampaignCreateRequest,
    OutreachCampaignResponse,
    OutreachCampaignUpdateRequest,
    OutreachMessageResponse,
)
from app.modules.outreach.service import OutreachService

router = APIRouter()


def get_outreach_service(db: Session = Depends(get_db_session)) -> OutreachService:
    """Dependency injection factory for OutreachService."""
    return OutreachService(db)


# =============================================================================
# Lead / Influencer Directory Endpoints
# =============================================================================


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import or create a new lead in the social CRM",
)
def create_lead(
    payload: LeadCreateRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> LeadResponse:
    lead = service.create_lead(payload.to_command())
    return LeadResponse.model_validate(lead)


@router.get(
    "/leads",
    response_model=list[LeadResponse],
    status_code=status.HTTP_200_OK,
    summary="List and filter tracked leads",
)
def list_leads(
    platform: PlatformType | None = Query(default=None, description="Filter by platform"),
    stage: LeadStage | None = Query(default=None, description="Filter by CRM relationship stage"),
    tier: LeadTier | None = Query(default=None, description="Filter by audience sizing tier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: OutreachService = Depends(get_outreach_service),
) -> list[LeadResponse]:
    leads = service.list_leads(
        platform=platform,
        stage=stage,
        tier=tier,
        limit=limit,
        offset=offset,
    )
    return [LeadResponse.model_validate(lead) for lead in leads]


@router.get(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a lead by ID",
)
def get_lead(
    lead_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> LeadResponse:
    lead = service.get_lead_by_id_or_raise(lead_id)
    return LeadResponse.model_validate(lead)


@router.patch(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    status_code=status.HTTP_200_OK,
    summary="Update lead metadata or relationship stage",
)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdateRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> LeadResponse:
    lead = service.update_lead(payload.to_command(lead_id))
    return LeadResponse.model_validate(lead)


@router.delete(
    "/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lead and their message history",
)
def delete_lead(
    lead_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> None:
    service.delete_lead(lead_id)


# =============================================================================
# Outreach Campaigns Endpoints
# =============================================================================


@router.post(
    "/campaigns",
    response_model=OutreachCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new cold outreach campaign",
)
def create_campaign(
    payload: OutreachCampaignCreateRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachCampaignResponse:
    campaign = service.create_campaign(payload.to_command())
    return OutreachCampaignResponse.model_validate(campaign)


@router.get(
    "/campaigns",
    response_model=list[OutreachCampaignResponse],
    status_code=status.HTTP_200_OK,
    summary="List all outreach campaigns",
)
def list_campaigns(
    is_active: bool | None = Query(default=None, description="Filter active status"),
    service: OutreachService = Depends(get_outreach_service),
) -> list[OutreachCampaignResponse]:
    campaigns = service.list_campaigns(is_active=is_active)
    return [OutreachCampaignResponse.model_validate(c) for c in campaigns]


@router.get(
    "/campaigns/{campaign_id}",
    response_model=OutreachCampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an outreach campaign by ID",
)
def get_campaign(
    campaign_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachCampaignResponse:
    campaign = service.get_campaign_by_id_or_raise(campaign_id)
    return OutreachCampaignResponse.model_validate(campaign)


@router.patch(
    "/campaigns/{campaign_id}",
    response_model=OutreachCampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Update outreach campaign settings or template",
)
def update_campaign(
    campaign_id: UUID,
    payload: OutreachCampaignUpdateRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachCampaignResponse:
    campaign = service.update_campaign(payload.to_command(campaign_id))
    return OutreachCampaignResponse.model_validate(campaign)


@router.delete(
    "/campaigns/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an outreach campaign",
)
def delete_campaign(
    campaign_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> None:
    service.delete_campaign(campaign_id)


# =============================================================================
# Outreach Messages & Review Gates Endpoints
# =============================================================================


@router.post(
    "/messages/stage",
    response_model=OutreachMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Stage a cold message behind a human approval gate",
)
def stage_message(
    payload: MessageStageRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachMessageResponse:
    message = service.stage_message(payload.to_command())
    return OutreachMessageResponse.model_validate(message)


@router.get(
    "/messages",
    response_model=list[OutreachMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="List staged, approved, or dispatched cold messages",
)
def list_messages(
    lead_id: UUID | None = Query(default=None, description="Filter by lead ID"),
    campaign_id: UUID | None = Query(default=None, description="Filter by campaign ID"),
    status: OutreachMessageStatus | None = Query(default=None, description="Filter by message review status"),
    limit: int = Query(default=50, ge=1, le=200),
    service: OutreachService = Depends(get_outreach_service),
) -> list[OutreachMessageResponse]:
    messages = service.list_messages(
        lead_id=lead_id,
        campaign_id=campaign_id,
        status=status,
        limit=limit,
    )
    return [OutreachMessageResponse.model_validate(m) for m in messages]


@router.get(
    "/messages/{message_id}",
    response_model=OutreachMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a cold outreach message by ID",
)
def get_message(
    message_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachMessageResponse:
    message = service.get_message_by_id_or_raise(message_id)
    return OutreachMessageResponse.model_validate(message)


@router.post(
    "/messages/{message_id}/review",
    response_model=OutreachMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a staged cold message",
)
def review_message(
    message_id: UUID,
    payload: MessageReviewRequest,
    service: OutreachService = Depends(get_outreach_service),
) -> OutreachMessageResponse:
    message = service.review_message(payload.to_command(message_id))
    return OutreachMessageResponse.model_validate(message)


@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a draft, staged, or rejected message",
)
def delete_message(
    message_id: UUID,
    service: OutreachService = Depends(get_outreach_service),
) -> None:
    service.delete_message(message_id)
