import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.common.enums import ActivitySeverity, ActivityType
from app.db.session import session_factory
from app.modules.accounts.service import AccountService
from app.modules.history.commands import LogActivityCommand
from app.modules.history.service import HistoryService
from app.modules.triggers.commands import EvaluateIncomingPostCommand
from app.modules.triggers.service import TriggerService
from app.platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)


async def run_watcher_worker(db: Session | None = None) -> int:
    """
    Periodic scraper polling loop:
    1. Iterates active WatchedHandles due for scraping.
    2. Resolves an active scraper profile for the target platform.
    3. Scrapes recent timeline posts.
    4. Evaluates posts against trigger rules and logs opportunities.
    """
    owns_session = db is None
    session = db or session_factory()
    matches_created = 0

    try:
        trigger_service = TriggerService(session)
        account_service = AccountService(session)
        history_service = HistoryService(session)

        watched_handles = trigger_service.list_watched_handles(active_only=True)
        if not watched_handles:
            return 0

        now = datetime.now(UTC)

        for handle in watched_handles:
            # Check scraping frequency interval
            if handle.last_scraped_at:
                cutoff = handle.last_scraped_at + timedelta(minutes=handle.scrape_frequency_minutes)
                if now < cutoff:
                    continue  # Not due yet

            # Find an active connected account on the same platform to act as browser scraper
            scraper_accounts = [
                acc for acc in account_service.list_accounts(active_only=True)
                if acc.platform == handle.platform and acc.status.value == "active"
            ]
            if not scraper_accounts:
                logger.debug("No active account available to scrape %s for @%s", handle.platform.value, handle.handle)
                continue

            scraper_account = scraper_accounts[0]

            try:
                adapter = PlatformRegistry.get_adapter(scraper_account)
                logger.info("Watcher: Scraping @%s on %s...", handle.handle, handle.platform.value)

                scraped_posts = await adapter.scrape_feed(handle.handle, limit=10)
                await adapter.close()

                # Evaluate each post against trigger rules
                for post in scraped_posts:
                    matches = trigger_service.evaluate_incoming_post(
                        EvaluateIncomingPostCommand(
                            platform=handle.platform,
                            platform_post_id=post.platform_post_id,
                            author_handle=post.author_handle,
                            post_content=post.content,
                            platform_post_url=post.platform_post_url,
                            watched_handle_id=handle.id,
                        )
                    )
                    for match in matches:
                        matches_created += 1
                        history_service.log_activity(
                            LogActivityCommand(
                                activity_type=ActivityType.TRIGGER_MATCHED,
                                severity=ActivitySeverity.INFO,
                                title=f"Opportunity detected from @{handle.handle}",
                                description=f"Matched keywords: {', '.join(match.matched_keywords)}",
                                entity_type="trigger_match",
                                entity_id=match.id,
                                actor="watcher_worker",
                            )
                        )

                # Update timestamp
                handle.last_scraped_at = now
                session.commit()

            except Exception as exc:
                logger.error("Watcher failed scraping @%s: %s", handle.handle, exc, exc_info=True)

        return matches_created

    finally:
        if owns_session:
            session.close()
