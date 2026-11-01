from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachMessageStatus,
    PlatformType,
)
from app.modules.accounts.exceptions import AccountNotFoundError
from app.modules.accounts.models import ConnectedAccount
from app.modules.accounts.service import AccountService
from app.modules.outreach.commands import (
    CreateLeadCommand,
    CreateOutreachCampaignCommand,
    RecordMessageDeliveryCommand,
    RecordMessageFailureCommand,
    ReviewMessageCommand,
    StageMessageCommand,
    UpdateLeadCommand,
    UpdateOutreachCampaignCommand,
)
from app.modules.outreach.exceptions import (
    DailyDMQuotaExceededError,
    LeadAlreadyExistsError,
    LeadNotFoundError,
    LeadUncontactableError,
    MessageAlreadyProcessedError,
    OutreachCampaignNotFoundError,
    OutreachMessageNotFoundError,
)
from app.modules.outreach.models import Lead, OutreachCampaign, OutreachMessage


def _ensure_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class OutreachService:
    def __init__(self, db: Session):
        self.db = db
        self.account_service = AccountService(db)

    # =========================================================================
    # Lead / Influencer Directory Management
    # =========================================================================

    def get_lead_by_id(self, lead_id: UUID | str) -> Lead | None:
        target_id = _ensure_uuid(lead_id)
        return (
            self.db.query(Lead)
            .filter(Lead.id == target_id)
            .first()
        )

    def get_lead_by_id_or_raise(self, lead_id: UUID | str) -> Lead:
        lead = self.get_lead_by_id(lead_id)
        if not lead:
            raise LeadNotFoundError(lead_id)
        return lead

    def get_lead_by_platform_and_handle(
        self, platform: PlatformType, handle: str
    ) -> Lead | None:
        clean_handle = handle.lstrip("@").strip()
        return (
            self.db.query(Lead)
            .filter(
                Lead.platform == platform,
                Lead.handle == clean_handle,
            )
            .first()
        )

    def list_leads(
        self,
        platform: PlatformType | None = None,
        stage: LeadStage | None = None,
        tier: LeadTier | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        query = self.db.query(Lead).order_by(Lead.created_at.desc())
        if platform is not None:
            query = query.filter(Lead.platform == platform)
        if stage is not None:
            query = query.filter(Lead.stage == stage)
        if tier is not None:
            query = query.filter(Lead.tier == tier)
        return query.offset(offset).limit(limit).all()

    def create_lead(self, cmd: CreateLeadCommand) -> Lead:
        clean_handle = cmd.handle.lstrip("@").strip()
        existing = self.get_lead_by_platform_and_handle(cmd.platform, clean_handle)
        if existing:
            platform_str = cmd.platform.value if hasattr(cmd.platform, "value") else str(cmd.platform)
            raise LeadAlreadyExistsError(platform=platform_str, handle=clean_handle)

        lead = Lead(
            platform=cmd.platform,
            handle=clean_handle,
            display_name=cmd.display_name,
            bio=cmd.bio,
            profile_url=cmd.profile_url,
            email=cmd.email,
            follower_count=cmd.follower_count,
            tier=cmd.tier,
            stage=cmd.stage,
            tags=cmd.tags,
            notes=cmd.notes,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def update_lead(self, cmd: UpdateLeadCommand) -> Lead:
        lead = self.get_lead_by_id_or_raise(cmd.lead_id)

        if cmd.display_name is not None:
            lead.display_name = cmd.display_name
        if cmd.bio is not None:
            lead.bio = cmd.bio
        if cmd.profile_url is not None:
            lead.profile_url = cmd.profile_url
        if cmd.email is not None:
            lead.email = cmd.email
        if cmd.follower_count is not None:
            lead.follower_count = cmd.follower_count
        if cmd.tier is not None:
            lead.tier = cmd.tier
        if cmd.stage is not None:
            lead.stage = cmd.stage
        if cmd.tags is not None:
            lead.tags = cmd.tags
        if cmd.notes is not None:
            lead.notes = cmd.notes
        if cmd.extra_metadata is not None:
            lead.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(lead)
        return lead

    def delete_lead(self, lead_id: UUID | str) -> None:
        lead = self.get_lead_by_id_or_raise(lead_id)
        # Purge dependent messages to guarantee cascade across all database dialects
        self.db.query(OutreachMessage).filter(OutreachMessage.lead_id == lead.id).delete(
            synchronize_session="fetch"
        )
        self.db.delete(lead)
        self.db.commit()

    # =========================================================================
    # Outreach Campaign Management
    # =========================================================================

    def get_campaign_by_id(self, campaign_id: UUID | str) -> OutreachCampaign | None:
        target_id = _ensure_uuid(campaign_id)
        return (
            self.db.query(OutreachCampaign)
            .filter(OutreachCampaign.id == target_id)
            .first()
        )

    def get_campaign_by_id_or_raise(self, campaign_id: UUID | str) -> OutreachCampaign:
        campaign = self.get_campaign_by_id(campaign_id)
        if not campaign:
            raise OutreachCampaignNotFoundError(campaign_id)
        return campaign

    def list_campaigns(self, is_active: bool | None = None) -> list[OutreachCampaign]:
        query = self.db.query(OutreachCampaign).order_by(OutreachCampaign.created_at.desc())
        if is_active is not None:
            query = query.filter(OutreachCampaign.is_active == is_active)
        return query.all()

    def create_campaign(self, cmd: CreateOutreachCampaignCommand) -> OutreachCampaign:
        # Verify account exists
        account = (
            self.db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == cmd.account_id)
            .first()
        )
        if not account:
            raise AccountNotFoundError(cmd.account_id)

        campaign = OutreachCampaign(
            name=cmd.name,
            account_id=cmd.account_id,
            description=cmd.description,
            is_active=cmd.is_active,
            target_criteria=cmd.target_criteria,
            template=cmd.template,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def update_campaign(self, cmd: UpdateOutreachCampaignCommand) -> OutreachCampaign:
        campaign = self.get_campaign_by_id_or_raise(cmd.campaign_id)

        if cmd.account_id is not None:
            account = (
                self.db.query(ConnectedAccount)
                .filter(ConnectedAccount.id == cmd.account_id)
                .first()
            )
            if not account:
                raise AccountNotFoundError(cmd.account_id)
            campaign.account_id = cmd.account_id

        if cmd.name is not None:
            campaign.name = cmd.name
        if cmd.description is not None:
            campaign.description = cmd.description
        if cmd.is_active is not None:
            campaign.is_active = cmd.is_active
        if cmd.target_criteria is not None:
            campaign.target_criteria = cmd.target_criteria
        if cmd.template is not None:
            campaign.template = cmd.template
        if cmd.extra_metadata is not None:
            campaign.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def delete_campaign(self, campaign_id: UUID | str) -> None:
        campaign = self.get_campaign_by_id_or_raise(campaign_id)
        # Detach messages from campaign before deletion
        self.db.query(OutreachMessage).filter(
            OutreachMessage.outreach_campaign_id == campaign.id
        ).update({OutreachMessage.outreach_campaign_id: None})
        self.db.delete(campaign)
        self.db.commit()

    # =========================================================================
    # Outreach Message Staging & Human Review Gates
    # =========================================================================

    def get_message_by_id(self, message_id: UUID | str) -> OutreachMessage | None:
        target_id = _ensure_uuid(message_id)
        return (
            self.db.query(OutreachMessage)
            .options(
                joinedload(OutreachMessage.lead),
                joinedload(OutreachMessage.account),
            )
            .filter(OutreachMessage.id == target_id)
            .first()
        )

    def get_message_by_id_or_raise(self, message_id: UUID | str) -> OutreachMessage:
        message = self.get_message_by_id(message_id)
        if not message:
            raise OutreachMessageNotFoundError(message_id)
        return message

    def list_messages(
        self,
        lead_id: UUID | None = None,
        campaign_id: UUID | None = None,
        status: OutreachMessageStatus | None = None,
        limit: int = 50,
    ) -> list[OutreachMessage]:
        query = (
            self.db.query(OutreachMessage)
            .options(
                joinedload(OutreachMessage.lead),
                joinedload(OutreachMessage.account),
            )
            .order_by(OutreachMessage.created_at.desc())
        )
        if lead_id is not None:
            query = query.filter(OutreachMessage.lead_id == lead_id)
        if campaign_id is not None:
            query = query.filter(OutreachMessage.outreach_campaign_id == campaign_id)
        if status is not None:
            query = query.filter(OutreachMessage.status == status)
        return query.limit(limit).all()

    def stage_message(self, cmd: StageMessageCommand) -> OutreachMessage:
        """
        Stages a cold message behind a human approval gate.
        Validates lead contactability and account availability.
        """
        lead = self.get_lead_by_id_or_raise(cmd.lead_id)
        if not lead.can_contact():
            raise LeadUncontactableError(handle=lead.handle, stage=lead.stage.value)

        account = (
            self.db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == cmd.account_id)
            .first()
        )
        if not account:
            raise AccountNotFoundError(cmd.account_id)

        if cmd.outreach_campaign_id:
            self.get_campaign_by_id_or_raise(cmd.outreach_campaign_id)

        message = OutreachMessage(
            lead_id=cmd.lead_id,
            account_id=cmd.account_id,
            outreach_campaign_id=cmd.outreach_campaign_id,
            channel=cmd.channel,
            content=cmd.content,
            status=OutreachMessageStatus.STAGED,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def review_message(self, cmd: ReviewMessageCommand) -> OutreachMessage:
        """
        Human-in-the-loop gate: Approves or rejects a staged cold message.
        When approving, validates account's safe anti-ban cold DM quota.
        """
        message = self.get_message_by_id_or_raise(cmd.message_id)
        if message.status not in (OutreachMessageStatus.STAGED, OutreachMessageStatus.DRAFT):
            raise MessageAlreadyProcessedError(message.id)

        if cmd.status == OutreachMessageStatus.APPROVED:
            # Check account anti-ban limits before approving
            account = (
                self.db.query(ConnectedAccount)
                .filter(ConnectedAccount.id == message.account_id)
                .first()
            )
            if account and not account.can_send_dm_today():
                raise DailyDMQuotaExceededError(
                    handle=account.handle,
                    limit=account.daily_dm_limit,
                )
            message.mark_as_approved(edited_content=cmd.edited_content)

        elif cmd.status == OutreachMessageStatus.REJECTED:
            message.mark_as_rejected(reason=cmd.rejection_reason)

        self.db.commit()
        self.db.refresh(message)
        return message

    def record_delivery(self, cmd: RecordMessageDeliveryCommand) -> OutreachMessage:
        """
        Records platform delivery, increments account's daily DM quota,
        and advances lead stage to 'contacted'.
        """
        message = self.get_message_by_id_or_raise(cmd.message_id)
        message.mark_as_dispatched(platform_id=cmd.platform_message_id)

        # Increment daily DM counter on the sender profile
        self.account_service.record_dm_activity(message.account_id)

        # Advance lead CRM stage if in discovery/qualification
        lead = self.get_lead_by_id(message.lead_id)
        if lead and lead.stage in (LeadStage.DISCOVERED, LeadStage.QUALIFIED):
            lead.stage = LeadStage.CONTACTED

        self.db.commit()
        self.db.refresh(message)
        return message

    def record_failure(self, cmd: RecordMessageFailureCommand) -> OutreachMessage:
        """Records platform delivery failure."""
        message = self.get_message_by_id_or_raise(cmd.message_id)
        message.mark_as_failed(error=cmd.error_message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def delete_message(self, message_id: UUID | str) -> None:
        """Permanently removes a draft, staged, or rejected message."""
        message = self.get_message_by_id_or_raise(message_id)
        if message.status == OutreachMessageStatus.DISPATCHED:
            raise MessageAlreadyProcessedError(message.id)

        self.db.delete(message)
        self.db.commit()
