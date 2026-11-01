from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.common.enums import CampaignStatus, PlatformType, PostStatus
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.service import AccountService
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
    RecordPostDeliveryCommand,
)
from app.modules.campaigns.service import CampaignService
from app.platforms.base import PublishResult
from app.platforms.browser.session_manager import BrowserSessionManager
from app.platforms.instagram.adapter import InstagramAdapter
from app.platforms.registry import PlatformRegistry


def test_platform_registry_to_campaign_dispatch_pipeline(db_session: Session, tmp_path: Path):
    """
    Verifies the complete integration flow:
    1. Account is registered in the DB.
    2. PlatformRegistry resolves the concrete InstagramAdapter.
    3. Campaign post is queued.
    4. Adapter simulated result finalizes post status and increments daily account quotas.
    """
    account_service = AccountService(db_session)
    campaign_service = CampaignService(db_session)

    # 1. Connect Account
    account = account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.INSTAGRAM,
            handle="brand_growth",
            display_name="Brand Growth",
            daily_post_limit=10,
        )
    )

    # 2. Verify Registry resolves InstagramAdapter
    session_mgr = BrowserSessionManager(base_dir=tmp_path / "sessions")
    adapter = PlatformRegistry.get_adapter(account, session_manager=session_mgr)
    assert isinstance(adapter, InstagramAdapter)
    assert adapter.account.id == account.id

    # 3. Queue Campaign Post
    campaign = campaign_service.create_campaign(
        CreateCampaignCommand(name="Integration Campaign", status=CampaignStatus.ACTIVE)
    )
    scheduled_post = campaign_service.queue_post(
        QueuePostCommand(
            campaign_id=campaign.id,
            account_id=account.id,
            content="Check out our new AI feature release! 🚀",
            media_urls=["storage/media/sample_post.jpg"],
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            status=PostStatus.SCHEDULED,
        )
    )
    assert scheduled_post.status == PostStatus.SCHEDULED

    # 4. Simulate Adapter Execution Result
    simulated_result = PublishResult(
        platform_post_id="ig_post_987654321",
        platform_post_url="https://www.instagram.com/p/ig_post_987654321/",
    )

    # 5. Record Delivery via CampaignService
    published_post = campaign_service.record_delivery(
        RecordPostDeliveryCommand(
            post_id=scheduled_post.id,
            platform_post_id=simulated_result.platform_post_id,
            platform_post_url=simulated_result.platform_post_url,
        )
    )

    # 6. Increment Sender Account Post Activity
    account_service.record_post_activity(account.id)

    # Assertions
    assert published_post.status == PostStatus.PUBLISHED
    assert published_post.platform_post_id == "ig_post_987654321"
    assert published_post.published_at is not None

    db_session.refresh(account)
    assert account.daily_posts_sent == 1
