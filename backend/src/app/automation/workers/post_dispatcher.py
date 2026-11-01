import logging

from sqlalchemy.orm import Session

from app.automation.throttler import account_throttler
from app.common.enums import ActivitySeverity, ActivityType, PostStatus
from app.db.session import session_factory
from app.modules.accounts.service import AccountService
from app.modules.campaigns.commands import (
    RecordPostDeliveryCommand,
    RecordPostFailureCommand,
)
from app.modules.campaigns.models import ScheduledPost
from app.modules.campaigns.service import CampaignService
from app.modules.history.commands import LogActivityCommand
from app.modules.history.service import HistoryService
from app.platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)


async def _dispatch_single_post(
    db: Session,
    post: ScheduledPost,
    campaign_service: CampaignService,
    account_service: AccountService,
    history_service: HistoryService,
) -> bool:
    """Executes the delivery of a single due post."""
    account = post.account

    # 1. Quota & Cooldown Safety Guards
    if not account.can_post_today():
        logger.warning("Account @%s cannot post today (quota or cooldown). Skipping post %s.", account.handle, post.id)
        return False

    # 2. Anti-Ban Throttling Slot Check
    acquired = await account_throttler.wait_and_acquire(account.id, max_wait_seconds=5.0)
    if not acquired:
        logger.info("Account @%s throttled for anti-ban pacing. Deferring post %s.", account.handle, post.id)
        return False

    # 3. Transition status to PUBLISHING
    post.mark_as_publishing()
    db.commit()

    # 4. Execute Platform Adapter
    try:
        adapter = PlatformRegistry.get_adapter(account)
        logger.info("Dispatching post %s via %s adapter for @%s...", post.id, account.platform.value, account.handle)

        result = await adapter.publish_post(
            content=post.content,
            media_paths=post.media_urls if post.media_urls else None,
        )
        await adapter.close()

        # 5. Record Success & Increment Quotas
        campaign_service.record_delivery(
            RecordPostDeliveryCommand(
                post_id=post.id,
                platform_post_id=result.platform_post_id,
                platform_post_url=result.platform_post_url,
            )
        )
        account_service.record_post_activity(account.id)

        history_service.log_activity(
            LogActivityCommand(
                activity_type=ActivityType.POST_PUBLISHED,
                severity=ActivitySeverity.SUCCESS,
                title=f"Post published on {account.platform.value}",
                description=f"Successfully posted to @{account.handle}.",
                entity_type="post",
                entity_id=post.id,
                actor="post_dispatcher",
            )
        )
        logger.info("✅ Post %s published successfully (ID: %s)", post.id, result.platform_post_id)
        return True

    except Exception as exc:
        logger.error("Failed to publish post %s for @%s: %s", post.id, account.handle, exc, exc_info=True)
        campaign_service.record_failure(
            RecordPostFailureCommand(
                post_id=post.id,
                error_message=str(exc),
            )
        )
        history_service.log_activity(
            LogActivityCommand(
                activity_type=ActivityType.POST_FAILED,
                severity=ActivitySeverity.ERROR,
                title=f"Post delivery failed on {account.platform.value}",
                description=str(exc),
                entity_type="post",
                entity_id=post.id,
                actor="post_dispatcher",
            )
        )
        return False


async def run_post_dispatcher(db: Session | None = None) -> int:
    """
    Polling worker cycle:
    1. Fetches due posts scheduled on or before current time.
    2. Dispatches each post through its platform adapter.
    3. Updates quotas and audit logs.
    """
    owns_session = db is None
    session = db or session_factory()
    dispatched_count = 0

    try:
        campaign_service = CampaignService(session)
        account_service = AccountService(session)
        history_service = HistoryService(session)

        due_posts = campaign_service.get_due_posts(limit=10)
        if not due_posts:
            return 0

        logger.info("PostDispatcher: Found %d due posts ready for delivery.", len(due_posts))

        for post in due_posts:
            # Re-verify status hasn't changed concurrently
            if post.status != PostStatus.SCHEDULED:
                continue

            success = await _dispatch_single_post(
                db=session,
                post=post,
                campaign_service=campaign_service,
                account_service=account_service,
                history_service=history_service,
            )
            if success:
                dispatched_count += 1

        return dispatched_count

    finally:
        if owns_session:
            session.close()
