from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.enums import (
    CampaignStatus,
    PlatformType,
    PostContentType,
    PostStatus,
)
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.exceptions import AccountNotFoundError
from app.modules.accounts.models import ConnectedAccount
from app.modules.accounts.service import AccountService
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
    RecordPostDeliveryCommand,
    RecordPostFailureCommand,
    UpdateCampaignCommand,
    UpdatePostCommand,
)
from app.modules.campaigns.exceptions import (
    CampaignInactiveError,
    CampaignNotFoundError,
    InvalidPostScheduleError,
    PostAlreadyPublishedError,
)
from app.modules.campaigns.service import CampaignService


def _create_sample_account(db: Session, handle: str = "growth_bot") -> ConnectedAccount:
    """Helper to register a connected account for post associations."""
    account_service = AccountService(db)
    return account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle=handle,
            display_name="Growth Bot",
        )
    )


# =============================================================================
# Campaign Unit Tests
# =============================================================================


def test_create_and_get_campaign(db_session: Session):
    service = CampaignService(db_session)
    cmd = CreateCampaignCommand(
        name="Launch Campaign",
        description="Q4 Marketing Strategy",
        status=CampaignStatus.ACTIVE,
        tags=["ai", "launch"],
    )

    campaign = service.create_campaign(cmd)

    assert campaign.id is not None
    assert campaign.name == "Launch Campaign"
    assert campaign.status == CampaignStatus.ACTIVE
    assert "launch" in campaign.tags

    queried = service.get_campaign_by_id_or_raise(campaign.id)
    assert queried.id == campaign.id


def test_get_campaign_not_found_raises(db_session: Session):
    service = CampaignService(db_session)
    with pytest.raises(CampaignNotFoundError):
        service.get_campaign_by_id_or_raise(uuid4())


def test_list_campaigns_with_filter(db_session: Session):
    service = CampaignService(db_session)
    service.create_campaign(CreateCampaignCommand(name="C1", status=CampaignStatus.ACTIVE))
    service.create_campaign(CreateCampaignCommand(name="C2", status=CampaignStatus.DRAFT))

    active = service.list_campaigns(status=CampaignStatus.ACTIVE)
    assert len(active) == 1
    assert active[0].name == "C1"

    all_campaigns = service.list_campaigns()
    assert len(all_campaigns) == 2


def test_update_campaign(db_session: Session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Old Name"))

    updated = service.update_campaign(
        UpdateCampaignCommand(
            campaign_id=campaign.id,
            name="New Name",
            status=CampaignStatus.PAUSED,
        )
    )

    assert updated.name == "New Name"
    assert updated.status == CampaignStatus.PAUSED


def test_delete_campaign_cascades_posts(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)

    campaign = service.create_campaign(CreateCampaignCommand(name="To Delete"))
    post = service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Post to be deleted",
            status=PostStatus.DRAFT,
        )
    )

    service.delete_campaign(campaign.id)

    assert service.get_campaign_by_id(campaign.id) is None
    assert service.get_post_by_id(post.id) is None


# =============================================================================
# Scheduled Post Unit Tests
# =============================================================================


def test_queue_post_success(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Active Camp"))

    scheduled_time = datetime.now(UTC) + timedelta(days=2)
    cmd = QueuePostCommand(
        campaign_id=campaign.id,
        account_id=account.id,
        content="Hello world! Check out our new AI tool.",
        content_type=PostContentType.TEXT,
        scheduled_at=scheduled_time,
    )

    post = service.queue_post(cmd)

    assert post.id is not None
    assert post.content == cmd.content
    assert post.status == PostStatus.SCHEDULED
    assert post.account_id == account.id


def test_queue_post_fails_on_inactive_campaign(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(
        CreateCampaignCommand(name="Archived Camp", status=CampaignStatus.ARCHIVED)
    )

    with pytest.raises(CampaignInactiveError):
        service.queue_post(
            QueuePostCommand(
                campaign_id=campaign.id,
                account_id=account.id,
                content="This should fail",
            )
        )


def test_queue_post_fails_on_nonexistent_account(db_session: Session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Active Camp"))

    with pytest.raises(AccountNotFoundError):
        service.queue_post(
            QueuePostCommand(
                campaign_id=campaign.id,
                account_id=uuid4(),
                content="No account",
            )
        )


def test_queue_post_fails_when_schedule_exceeds_campaign_end_date(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)

    campaign_end = datetime.now(UTC) + timedelta(days=5)
    campaign = service.create_campaign(
        CreateCampaignCommand(name="Time-bound", end_date=campaign_end)
    )

    with pytest.raises(InvalidPostScheduleError):
        service.queue_post(
            QueuePostCommand(
                campaign_id=campaign.id,
                account_id=account.id,
                content="Too late",
                scheduled_at=campaign_end + timedelta(days=1),
            )
        )


def test_update_and_cancel_post(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Camp"))

    post = service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Draft copy",
            status=PostStatus.DRAFT,
        )
    )

    updated = service.update_post(
        UpdatePostCommand(
            post_id=post.id,
            content="Polished copy",
        )
    )
    assert updated.content == "Polished copy"

    cancelled = service.cancel_post(post.id)
    assert cancelled.status == PostStatus.CANCELLED


def test_published_post_cannot_be_modified_or_deleted(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Camp"))

    post = service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Already sent",
            status=PostStatus.DRAFT,
        )
    )

    # Deliver post
    service.record_delivery(
        RecordPostDeliveryCommand(
            post_id=post.id,
            platform_post_id="tweet_123",
            platform_post_url="https://x.com/post/123",
        )
    )
    assert post.status == PostStatus.PUBLISHED
    assert post.platform_post_id == "tweet_123"

    # Modifying published post must raise
    with pytest.raises(PostAlreadyPublishedError):
        service.update_post(UpdatePostCommand(post_id=post.id, content="Change"))

    # Deleting published post must raise
    with pytest.raises(PostAlreadyPublishedError):
        service.delete_post(post.id)


def test_get_due_posts_worker_query(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Camp"))

    now = datetime.now(UTC)

    # Due post (scheduled 10 minutes ago)
    service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Due now",
            scheduled_at=now - timedelta(minutes=10),
            status=PostStatus.SCHEDULED,
        )
    )

    # Future post (scheduled 1 hour from now)
    service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Future post",
            scheduled_at=now + timedelta(hours=1),
            status=PostStatus.SCHEDULED,
        )
    )

    due_posts = service.get_due_posts(limit=10)
    assert len(due_posts) == 1
    assert due_posts[0].content == "Due now"


def test_record_failure_retry_mechanism(db_session: Session):
    service = CampaignService(db_session)
    account = _create_sample_account(db_session)
    campaign = service.create_campaign(CreateCampaignCommand(name="Camp"))

    post = service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Retriable post",
            max_retries=2,
            status=PostStatus.SCHEDULED,
        )
    )

    # 1st failure -> stays SCHEDULED for retry
    service.record_failure(RecordPostFailureCommand(post_id=post.id, error_message="Rate limit 429"))
    assert post.retry_count == 1
    assert post.status == PostStatus.SCHEDULED

    # 2nd failure -> reaches max_retries, transitions to FAILED
    service.record_failure(RecordPostFailureCommand(post_id=post.id, error_message="Rate limit 429"))
    assert post.retry_count == 2
    assert post.status == PostStatus.FAILED
    assert post.last_error_message == "Rate limit 429"
