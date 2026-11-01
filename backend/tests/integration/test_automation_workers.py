import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.automation.scheduler import (
    start_scheduler,
    stop_scheduler,
)
from app.automation.throttler import account_throttler
from app.automation.workers.post_dispatcher import run_post_dispatcher
from app.automation.workers.quota_reset_worker import run_quota_reset_worker
from app.automation.workers.watcher_worker import run_watcher_worker
from app.common.enums import (
    CampaignStatus,
    PlatformType,
    PostStatus,
    TriggerActionType,
    TriggerMatchStatus,
)
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.service import AccountService
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
)
from app.modules.campaigns.service import CampaignService
from app.modules.history.service import HistoryService
from app.modules.triggers.commands import (
    AddWatchedHandleCommand,
    CreateTriggerRuleCommand,
)
from app.modules.triggers.service import TriggerService
from app.platforms.base import BasePlatformAdapter, PublishResult, ScrapedPost
from app.platforms.registry import PlatformRegistry
from app.platforms.twitter.adapter import TwitterAdapter


class MockAutomationAdapter(BasePlatformAdapter):
    """Mock platform adapter verifying worker interactions without network requests."""

    async def authenticate(self) -> bool:
        return True

    async def publish_post(
        self, content: str, media_paths: list[str] | None = None
    ) -> PublishResult:
        _ = (content, media_paths)
        return PublishResult(
            platform_post_id="mock_post_123",
            platform_post_url="https://mock.platform/post/123",
        )

    async def send_dm(self, recipient_handle: str, message_text: str) -> str:
        _ = (recipient_handle, message_text)
        return "mock_dm_123"

    async def scrape_feed(self, target_handle: str, limit: int = 15) -> list[ScrapedPost]:
        _ = limit
        return [
            ScrapedPost(
                platform_post_id="tweet_scraped_999",
                author_handle=target_handle,
                content="Looking for a solid alternative to expensive legacy tools.",
                platform_post_url=f"https://mock.platform/{target_handle}/status/999",
            )
        ]

    async def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def register_mock_adapter():
    """
    Temporarily registers MockAutomationAdapter for TWITTER and safely restores
    TwitterAdapter upon test teardown to prevent test isolation pollution.
    """
    original_adapter = PlatformRegistry._registry.get(PlatformType.TWITTER, TwitterAdapter)
    PlatformRegistry.register(PlatformType.TWITTER, MockAutomationAdapter)
    try:
        yield
    finally:
        PlatformRegistry.register(PlatformType.TWITTER, original_adapter)


# =============================================================================
# Post Dispatcher Worker Tests
# =============================================================================


@pytest.mark.anyio
async def test_post_dispatcher_success_flow(db_session: Session):
    account_service = AccountService(db_session)
    campaign_service = CampaignService(db_session)
    history_service = HistoryService(db_session)

    # 1. Seed connected account
    account = account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="dispatcher_bot",
            daily_post_limit=10,
        )
    )
    await account_throttler.reset(account.id)

    # 2. Seed active campaign & due post (scheduled in the past)
    campaign = campaign_service.create_campaign(
        CreateCampaignCommand(name="Auto Campaign", status=CampaignStatus.ACTIVE)
    )
    post = campaign_service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Automated background post content",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=5),
            status=PostStatus.SCHEDULED,
        )
    )

    # 3. Run Post Dispatcher Worker
    dispatched = await run_post_dispatcher(db=db_session)
    assert dispatched == 1

    # 4. Verify post status advanced to PUBLISHED
    refreshed_post = campaign_service.get_post_by_id_or_raise(post.id)
    assert refreshed_post.status == PostStatus.PUBLISHED
    assert refreshed_post.platform_post_id == "mock_post_123"

    # 5. Verify account daily quota incremented
    db_session.refresh(account)
    assert account.daily_posts_sent == 1

    # 6. Verify audit trail logged
    logs = history_service.list_activities(entity_id=post.id)
    assert len(logs) == 1
    assert logs[0].activity_type.value == "post_published"


@pytest.mark.anyio
async def test_post_dispatcher_skips_when_quota_exhausted(db_session: Session):
    account_service = AccountService(db_session)
    campaign_service = CampaignService(db_session)

    account = account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="exhausted_bot",
            daily_post_limit=1,
        )
    )
    account.daily_posts_sent = 1
    db_session.commit()

    campaign = campaign_service.create_campaign(
        CreateCampaignCommand(name="Camp", status=CampaignStatus.ACTIVE)
    )
    post = campaign_service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Cannot be posted",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            status=PostStatus.SCHEDULED,
        )
    )

    dispatched = await run_post_dispatcher(db=db_session)
    assert dispatched == 0

    refreshed = campaign_service.get_post_by_id_or_raise(post.id)
    assert refreshed.status == PostStatus.SCHEDULED  # Remains waiting


# =============================================================================
# Competitor Feed Watcher Worker Tests
# =============================================================================


@pytest.mark.anyio
async def test_watcher_worker_scrapes_and_generates_matches(db_session: Session):
    account_service = AccountService(db_session)
    trigger_service = TriggerService(db_session)

    # 1. Seed active scraper profile
    scraper = account_service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="scraper_account")
    )

    # 2. Seed watched competitor handle
    handle = trigger_service.add_watched_handle(
        AddWatchedHandleCommand(
            platform=PlatformType.TWITTER,
            handle="@competitor_brand",
            scrape_frequency_minutes=5,
        )
    )

    # 3. Seed trigger rule looking for 'alternative' keyword
    trigger_service.create_rule(
        CreateTriggerRuleCommand(
            name="Alternative Keyword Rule",
            platform=PlatformType.TWITTER,
            account_id=scraper.id,
            watched_handle_id=handle.id,
            action_type=TriggerActionType.STAGE_DRAFT,
            keywords_any=["alternative"],
            response_template="Hey @{author}, check our open-source solution!",
        )
    )

    # 4. Run Watcher Worker
    matches_created = await run_watcher_worker(db=db_session)
    assert matches_created == 1

    # 5. Verify match created in DB
    matches = trigger_service.list_matches()
    assert len(matches) == 1
    assert matches[0].platform_post_id == "tweet_scraped_999"
    assert matches[0].status == TriggerMatchStatus.PENDING_REVIEW

    # 6. Verify handle's last_scraped_at timestamp updated
    db_session.refresh(handle)
    assert handle.last_scraped_at is not None


# =============================================================================
# Quota Reset & Cloud Sync Worker Tests
# =============================================================================


@pytest.mark.anyio
async def test_quota_reset_worker(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    account_service = AccountService(db_session)

    # Mock sync_replica so tests do not attempt cloud networking
    mock_sync = MagicMock()
    monkeypatch.setattr("app.automation.workers.quota_reset_worker.sync_replica", mock_sync)

    # Seed account whose reset timestamp was 25 hours ago
    account = account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="stale_counter_bot",
            daily_post_limit=10,
        )
    )
    account.daily_posts_sent = 5
    account.daily_dms_sent = 8
    account.daily_counters_reset_at = datetime.now(UTC) - timedelta(hours=25)
    db_session.commit()

    reset_count = await run_quota_reset_worker(db=db_session)
    assert reset_count == 1

    # Verify counts reset to 0
    db_session.refresh(account)
    assert account.daily_posts_sent == 0
    assert account.daily_dms_sent == 0
    mock_sync.assert_called_once()


# =============================================================================
# APScheduler Lifecycle Tests
# =============================================================================


@pytest.mark.anyio
async def test_scheduler_lifecycle():
    from app.automation.scheduler import (
        get_scheduler,
    )

    # 1. Start within active event loop
    start_scheduler()
    sched = get_scheduler()
    assert sched.running is True

    # 2. Verify all 3 worker jobs are scheduled
    job_ids = [job.id for job in sched.get_jobs()]
    assert "post_dispatcher_job" in job_ids
    assert "watcher_worker_job" in job_ids
    assert "quota_reset_job" in job_ids

    # 3. Stop scheduler and yield one tick to event loop for _shutdown callback
    stop_scheduler()
    await asyncio.sleep(0.01)
    assert sched.running is False
