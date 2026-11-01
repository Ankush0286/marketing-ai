from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachChannel,
    OutreachMessageStatus,
    PlatformType,
)
from app.modules.accounts.commands import CreateAccountCommand
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
from app.modules.outreach.models import Lead
from app.modules.outreach.service import OutreachService


def _create_sample_account(
    db: Session, handle: str = "outreach_bot", daily_dm_limit: int = 15
) -> ConnectedAccount:
    """Helper to create a connected account used for cold DM outreach."""
    account_service = AccountService(db)
    return account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle=handle,
            display_name="Outreach Bot",
            daily_dm_limit=daily_dm_limit,
        )
    )


def _create_sample_lead(
    service: OutreachService,
    handle: str = "influencer_sam",
    stage: LeadStage = LeadStage.DISCOVERED,
) -> Lead:
    """Helper to create a lead in the social CRM."""
    return service.create_lead(
        CreateLeadCommand(
            platform=PlatformType.TWITTER,
            handle=handle,
            display_name="Influencer Sam",
            follower_count=25000,
            tier=LeadTier.MICRO,
            stage=stage,
            tags=["tech", "saas"],
        )
    )


# =============================================================================
# Lead / Influencer Directory Unit Tests
# =============================================================================


def test_lead_crud(db_session: Session):
    service = OutreachService(db_session)

    # 1. Create lead (strips leading @)
    cmd = CreateLeadCommand(
        platform=PlatformType.TWITTER,
        handle="@startup_ceo",
        display_name="Startup CEO",
        bio="Building the future of marketing automation.",
        follower_count=12000,
        tier=LeadTier.MICRO,
    )
    lead = service.create_lead(cmd)

    assert lead.id is not None
    assert lead.handle == "startup_ceo"
    assert lead.stage == LeadStage.DISCOVERED
    assert lead.tier == LeadTier.MICRO

    # 2. Update lead
    updated = service.update_lead(
        UpdateLeadCommand(
            lead_id=lead.id,
            display_name="Renamed CEO",
            stage=LeadStage.QUALIFIED,
            notes="Very responsive on tech discussions.",
        )
    )
    assert updated.display_name == "Renamed CEO"
    assert updated.stage == LeadStage.QUALIFIED
    assert updated.notes == "Very responsive on tech discussions."

    # 3. List leads
    leads = service.list_leads(stage=LeadStage.QUALIFIED)
    assert len(leads) == 1
    assert leads[0].id == lead.id

    # 4. Delete lead
    service.delete_lead(lead.id)
    assert service.get_lead_by_id(lead.id) is None


def test_create_duplicate_lead_raises(db_session: Session):
    service = OutreachService(db_session)
    service.create_lead(
        CreateLeadCommand(platform=PlatformType.TWITTER, handle="unique_creator")
    )

    with pytest.raises(LeadAlreadyExistsError):
        service.create_lead(
            CreateLeadCommand(platform=PlatformType.TWITTER, handle="@unique_creator")
        )


def test_get_nonexistent_lead_raises(db_session: Session):
    service = OutreachService(db_session)
    with pytest.raises(LeadNotFoundError):
        service.get_lead_by_id_or_raise(uuid4())


# =============================================================================
# Outreach Campaigns Unit Tests
# =============================================================================


def test_outreach_campaign_crud(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)

    # 1. Create campaign
    cmd = CreateOutreachCampaignCommand(
        name="Micro-Influencer Q4",
        account_id=account.id,
        template="Hey @{handle}, love your content on SaaS!",
        target_criteria={"min_followers": 5000, "max_followers": 50000},
    )
    campaign = service.create_campaign(cmd)

    assert campaign.id is not None
    assert campaign.name == "Micro-Influencer Q4"
    assert campaign.is_active is True

    # 2. Update campaign
    updated = service.update_campaign(
        UpdateOutreachCampaignCommand(
            campaign_id=campaign.id,
            name="Updated Campaign Name",
            is_active=False,
        )
    )
    assert updated.name == "Updated Campaign Name"
    assert updated.is_active is False

    # 3. Delete campaign
    service.delete_campaign(campaign.id)
    assert service.get_campaign_by_id(campaign.id) is None


def test_create_campaign_nonexistent_account_raises(db_session: Session):
    service = OutreachService(db_session)
    with pytest.raises(AccountNotFoundError):
        service.create_campaign(
            CreateOutreachCampaignCommand(
                name="Orphan Campaign",
                account_id=uuid4(),
            )
        )


def test_get_nonexistent_campaign_raises(db_session: Session):
    service = OutreachService(db_session)
    with pytest.raises(OutreachCampaignNotFoundError):
        service.get_campaign_by_id_or_raise(uuid4())


# =============================================================================
# Message Staging & Human Review Gates Unit Tests
# =============================================================================


def test_stage_message_success(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)
    lead = _create_sample_lead(service, "prospect_one")

    cmd = StageMessageCommand(
        lead_id=lead.id,
        account_id=account.id,
        content="Hey Sam, noticed your post on AI workflows. Would love to connect!",
        channel=OutreachChannel.DM,
    )
    message = service.stage_message(cmd)

    assert message.id is not None
    assert message.status == OutreachMessageStatus.STAGED
    assert message.lead_id == lead.id
    assert message.account_id == account.id


def test_stage_message_uncontactable_lead_raises(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)

    # Lead marked 'do_not_contact'
    dnc_lead = _create_sample_lead(service, "optout_user", stage=LeadStage.DO_NOT_CONTACT)
    with pytest.raises(LeadUncontactableError):
        service.stage_message(
            StageMessageCommand(
                lead_id=dnc_lead.id,
                account_id=account.id,
                content="Hello there!",
            )
        )

    # Lead marked 'converted'
    converted_lead = _create_sample_lead(service, "customer_user", stage=LeadStage.CONVERTED)
    with pytest.raises(LeadUncontactableError):
        service.stage_message(
            StageMessageCommand(
                lead_id=converted_lead.id,
                account_id=account.id,
                content="Hello customer!",
            )
        )


def test_review_message_approval_and_rejection(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)
    lead = _create_sample_lead(service, "review_lead")

    # 1. Approval flow with copy edits
    msg1 = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Draft copy that needs polish.",
        )
    )
    approved = service.review_message(
        ReviewMessageCommand(
            message_id=msg1.id,
            status=OutreachMessageStatus.APPROVED,
            edited_content="Polished, personalized cold DM copy.",
        )
    )
    assert approved.status == OutreachMessageStatus.APPROVED
    assert approved.content == "Polished, personalized cold DM copy."
    assert approved.reviewed_at is not None

    # 2. Rejection flow with reason
    msg2 = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Irrelevant pitch message.",
        )
    )
    rejected = service.review_message(
        ReviewMessageCommand(
            message_id=msg2.id,
            status=OutreachMessageStatus.REJECTED,
            rejection_reason="Not a good fit for this campaign.",
        )
    )
    assert rejected.status == OutreachMessageStatus.REJECTED
    assert rejected.last_error_message == "Not a good fit for this campaign."


def test_review_message_dm_quota_exceeded_raises(db_session: Session):
    """Enforces that approving a message checks the account's safe daily cold DM limits."""
    service = OutreachService(db_session)
    # Account with daily limit of 1 DM
    account = _create_sample_account(db_session, "limited_dm_bot", daily_dm_limit=1)
    lead = _create_sample_lead(service, "quota_lead")

    # Exhaust the daily DM limit on the sender account
    account.daily_dms_sent = 1
    db_session.commit()

    staged = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Pitch message",
        )
    )

    # Attempting to approve must fail due to anti-ban quota enforcement
    with pytest.raises(DailyDMQuotaExceededError):
        service.review_message(
            ReviewMessageCommand(
                message_id=staged.id,
                status=OutreachMessageStatus.APPROVED,
            )
        )


def test_record_delivery_advances_lead_stage_and_increments_quota(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)
    lead = _create_sample_lead(service, "dispatched_lead", stage=LeadStage.DISCOVERED)

    message = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Hey there, great profile!",
        )
    )

    # Approve message
    service.review_message(
        ReviewMessageCommand(message_id=message.id, status=OutreachMessageStatus.APPROVED)
    )

    # Platform adapter confirms DM dispatch
    delivered = service.record_delivery(
        RecordMessageDeliveryCommand(
            message_id=message.id,
            platform_message_id="dm_platform_12345",
        )
    )

    assert delivered.status == OutreachMessageStatus.DISPATCHED
    assert delivered.platform_message_id == "dm_platform_12345"
    assert delivered.sent_at is not None

    # Verify CRM lead progressed from DISCOVERED -> CONTACTED
    refreshed_lead = service.get_lead_by_id_or_raise(lead.id)
    assert refreshed_lead.stage == LeadStage.CONTACTED

    # Verify sender profile daily DM count incremented
    db_session.refresh(account)
    assert account.daily_dms_sent == 1


def test_record_failure(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)
    lead = _create_sample_lead(service, "failure_lead")

    message = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Hello world!",
        )
    )

    failed = service.record_failure(
        RecordMessageFailureCommand(
            message_id=message.id,
            error_message="Twitter API rate limited (429)",
        )
    )
    assert failed.status == OutreachMessageStatus.FAILED
    assert failed.last_error_message == "Twitter API rate limited (429)"


def test_processed_message_cannot_be_reviewed_or_deleted(db_session: Session):
    service = OutreachService(db_session)
    account = _create_sample_account(db_session)
    lead = _create_sample_lead(service, "immutable_lead")

    message = service.stage_message(
        StageMessageCommand(
            lead_id=lead.id,
            account_id=account.id,
            content="Already sent copy",
        )
    )
    service.record_delivery(
        RecordMessageDeliveryCommand(
            message_id=message.id,
            platform_message_id="platform_sent_999",
        )
    )

    # Re-reviewing already sent message must raise
    with pytest.raises(MessageAlreadyProcessedError):
        service.review_message(
            ReviewMessageCommand(
                message_id=message.id,
                status=OutreachMessageStatus.APPROVED,
            )
        )

    # Deleting sent message must raise
    with pytest.raises(MessageAlreadyProcessedError):
        service.delete_message(message.id)


def test_get_nonexistent_message_raises(db_session: Session):
    service = OutreachService(db_session)
    with pytest.raises(OutreachMessageNotFoundError):
        service.get_message_by_id_or_raise(uuid4())
