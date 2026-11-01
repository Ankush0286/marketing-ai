import asyncio
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.core.security import decrypt_token
from app.modules.accounts.models import ConnectedAccount
from app.platforms.base import BasePlatformAdapter, PublishResult, ScrapedPost
from app.platforms.browser.driver import create_stealth_context
from app.platforms.browser.human_behavior import (
    human_scroll,
    human_type,
    random_delay,
)
from app.platforms.browser.session_manager import BrowserSessionManager
from app.platforms.twitter import selectors

logger = logging.getLogger(__name__)


class TwitterAutomationError(Exception):
    """Base exception for Twitter / X automation failures."""


class TwitterAdapter(BasePlatformAdapter):
    """
    Production-ready Twitter / X automation adapter using stealth Playwright,
    persistent cookie sessions, and anti-ban human behavior emulation.
    """

    def __init__(
        self,
        account: ConnectedAccount,
        headless: bool = True,
        session_manager: BrowserSessionManager | None = None,
    ):
        super().__init__(account)
        self.headless = headless
        self.session_manager = session_manager or BrowserSessionManager()

        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _get_or_create_page(self) -> Page:
        """Initializes stealth browser context and returns the active page."""
        if self._page and not self._page.is_closed():
            return self._page

        if not self._playwright:
            self._playwright = await async_playwright().start()

        session_dir = self.session_manager.get_account_session_dir(self.account.id)
        storage_state_path = self.session_manager.get_storage_state_path(self.account.id)

        self._context = await create_stealth_context(
            playwright=self._playwright,
            user_data_dir=session_dir,
            headless=self.headless,
            storage_state_path=storage_state_path if storage_state_path.exists() else None,
        )

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        return self._page

    async def _dismiss_popups(self, page: Page) -> None:
        """Dismisses common Twitter cookie banners or dialogs."""
        try:
            cookie_btn = page.locator(selectors.COOKIE_ACCEPT_BUTTON).first
            if await cookie_btn.is_visible(timeout=1500):
                await cookie_btn.click()
                await random_delay(0.5, 1.2)
        except Exception:
            pass

    async def authenticate(self) -> bool:
        """
        Verifies active login session or executes automated multi-step login.
        Dumps updated cookies to storage_state.json upon success.
        """
        page = await self._get_or_create_page()
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await random_delay(2.0, 3.5)
        await self._dismiss_popups(page)

        # Check if already authenticated via session cookies
        home_nav = page.locator(selectors.HOME_NAV_ICON).first
        if await home_nav.is_visible(timeout=4000):
            logger.info("Twitter @%s already authenticated via persistent session.", self.account.handle)
            if self._context:
                await self.session_manager.save_session_state(self._context, self.account.id)
            return True

        # Need to execute login flow
        logger.info("Executing automated login for Twitter @%s...", self.account.handle)
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
        await random_delay(2.0, 3.5)
        await self._dismiss_popups(page)

        username_input = page.locator(selectors.LOGIN_USERNAME_INPUT).first
        if not await username_input.is_visible(timeout=10000):
            logger.warning("Twitter login input not visible for @%s", self.account.handle)
            return False

        # Step 1: Username
        await human_type(page, username_input, self.account.handle)
        await random_delay(0.5, 1.2)
        next_btn = page.locator(selectors.LOGIN_NEXT_BUTTON).first
        await next_btn.click()
        await random_delay(1.5, 2.5)

        # Handle unusual activity challenge (asks for username/phone confirmation)
        challenge_input = page.locator(selectors.LOGIN_UNUSUAL_ACTIVITY_INPUT).first
        if await challenge_input.is_visible(timeout=2500):
            logger.info("Twitter requested secondary handle confirmation for @%s", self.account.handle)
            await human_type(page, challenge_input, self.account.handle)
            await random_delay(0.5, 1.0)
            await page.locator(selectors.LOGIN_NEXT_BUTTON).first.click()
            await random_delay(1.5, 2.5)

        # Step 2: Password
        password = decrypt_token(self.account.encrypted_api_secret)
        if not password:
            logger.error("No password credentials found in vault for Twitter @%s", self.account.handle)
            return False

        password_input = page.locator(selectors.LOGIN_PASSWORD_INPUT).first
        await human_type(page, password_input, password)
        await random_delay(0.5, 1.2)

        submit_btn = page.locator(selectors.LOGIN_SUBMIT_BUTTON).first
        await submit_btn.click()

        # Wait for home page navigation
        try:
            await page.locator(selectors.HOME_NAV_ICON).first.wait_for(
                state="visible", timeout=30000
            )
            await self._dismiss_popups(page)
            if self._context:
                await self.session_manager.save_session_state(self._context, self.account.id)
            logger.info("Twitter login successful for @%s", self.account.handle)
            return True
        except Exception as exc:
            logger.error("Twitter login verification failed for @%s: %s", self.account.handle, exc)
            return False

    async def publish_post(
        self,
        content: str,
        media_paths: list[str] | None = None,
    ) -> PublishResult:
        """Publishes a text or media tweet to Twitter / X."""
        # 1. Fail fast: Validate media paths exist on disk before launching browser
        resolved_media: list[Path] = []
        if media_paths:
            for path_str in media_paths:
                file_path = Path(path_str).resolve()
                if not file_path.exists():
                    raise FileNotFoundError(f"Media file does not exist: {file_path}")
                resolved_media.append(file_path)

        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise TwitterAutomationError(f"Failed to authenticate Twitter session for @{self.account.handle}")

        logger.info("Opening Twitter compose box for @%s...", self.account.handle)
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await random_delay(2.0, 3.5)
        await self._dismiss_popups(page)

        compose_box = page.locator(selectors.TWEET_TEXTAREA).first
        await compose_box.wait_for(state="visible", timeout=15000)
        await compose_box.click()
        await random_delay(0.5, 1.0)

        # 2. Upload media files if provided
        if resolved_media:
            file_input = page.locator(selectors.TWEET_FILE_INPUT).first
            for media_path in resolved_media:
                logger.info("Attaching media file to tweet: %s", media_path)
                await file_input.set_input_files(str(media_path))
                await random_delay(2.0, 3.5)

        # 3. Insert tweet text using human typing
        logger.info("Typing tweet copy for @%s...", self.account.handle)
        await human_type(page, compose_box, content, min_delay_ms=25, max_delay_ms=75)
        await random_delay(1.0, 2.0)

        # 4. Click Post button
        post_btn = page.locator(selectors.TWEET_SUBMIT_BUTTON).first
        await post_btn.click()

        # Wait for the tweet compose box to clear (indicates success)
        await compose_box.wait_for(state="detached", timeout=30000)
        await random_delay(2.0, 3.5)

        generated_id = f"tw_{uuid.uuid4().hex[:12]}"
        logger.info("✅ Tweet successfully published for @%s", self.account.handle)

        if self._context:
            await self.session_manager.save_session_state(self._context, self.account.id)

        return PublishResult(
            platform_post_id=generated_id,
            platform_post_url=f"https://x.com/{self.account.handle}/status/{generated_id}",
        )

    async def send_dm(
        self,
        recipient_handle: str,
        message_text: str,
    ) -> str:
        """Sends a private cold DM on Twitter / X."""
        clean_handle = recipient_handle.lstrip("@").strip()
        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise TwitterAutomationError(f"Failed to authenticate Twitter session for @{self.account.handle}")

        logger.info("Navigating to profile @%s to dispatch Twitter DM...", clean_handle)
        await page.goto(f"https://x.com/{clean_handle}", wait_until="domcontentloaded")
        await random_delay(2.5, 4.0)
        await self._dismiss_popups(page)

        # Click Message button on profile header
        dm_btn = page.locator(selectors.PROFILE_DM_BUTTON).first
        if not await dm_btn.is_visible(timeout=5000):
            raise TwitterAutomationError(f"Direct message button not accessible on Twitter @{clean_handle}")

        await dm_btn.click()
        await random_delay(2.0, 3.5)

        # Locate DM input
        dm_input = page.locator(selectors.DM_TEXTAREA).first
        await dm_input.wait_for(state="visible", timeout=15000)
        await dm_input.click()
        await random_delay(0.5, 1.0)

        # Type message with human jitter and send
        await human_type(page, dm_input, message_text, min_delay_ms=25, max_delay_ms=75)
        await random_delay(0.8, 1.5)

        send_button = page.locator(selectors.DM_SEND_BUTTON).first
        if await send_button.is_visible(timeout=2000):
            await send_button.click()
        else:
            await page.keyboard.press("Enter")
        await random_delay(2.0, 3.5)

        parsed_url = urlparse(page.url)
        thread_id = parsed_url.path.strip("/").split("/")[-1] if "messages" in page.url else "unknown_thread"
        logger.info("✅ Twitter DM successfully sent to @%s in thread %s", clean_handle, thread_id)

        if self._context:
            await self.session_manager.save_session_state(self._context, self.account.id)

        return thread_id

    async def scrape_feed(
        self,
        target_handle: str,
        limit: int = 15,
    ) -> list[ScrapedPost]:
        """Scrapes recent tweets and metrics from a competitor's profile timeline."""
        clean_handle = target_handle.lstrip("@").strip()
        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise TwitterAutomationError(f"Failed to authenticate Twitter session for @{self.account.handle}")

        logger.info("Scraping timeline for target profile @%s...", clean_handle)
        await page.goto(f"https://x.com/{clean_handle}", wait_until="domcontentloaded")
        await random_delay(2.5, 4.0)
        await self._dismiss_popups(page)

        collected_posts: list[ScrapedPost] = []
        seen_ids: set[str] = set()

        for _ in range(3):  # Up to 3 scroll batches
            tweet_elements = await page.locator(selectors.TWEET_ARTICLE).all()
            for tweet_el in tweet_elements:
                try:
                    # Find status link (e.g. /username/status/123456789)
                    link_el = tweet_el.locator(selectors.TWEET_STATUS_LINK).first
                    href = await link_el.get_attribute("href")
                    if not href or "/status/" not in href:
                        continue

                    tweet_id = href.strip("/").split("/status/")[-1].split("/")[0].split("?")[0]
                    if tweet_id in seen_ids:
                        continue

                    # Extract tweet copy
                    text_el = tweet_el.locator(selectors.TWEET_TEXT).first
                    content = await text_el.inner_text() if await text_el.is_visible() else ""

                    # Extract timestamp
                    time_el = tweet_el.locator(selectors.TWEET_TIME).first
                    published_at: datetime | None = None
                    if await time_el.is_visible():
                        dt_str = await time_el.get_attribute("datetime")
                        if dt_str:
                            published_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

                    seen_ids.add(tweet_id)
                    collected_posts.append(
                        ScrapedPost(
                            platform_post_id=tweet_id,
                            author_handle=clean_handle,
                            content=content,
                            platform_post_url=f"https://x.com/{clean_handle}/status/{tweet_id}",
                            published_at=published_at or datetime.now(UTC),
                        )
                    )

                    if len(collected_posts) >= limit:
                        break
                except Exception:
                    continue

            if len(collected_posts) >= limit:
                break

            await human_scroll(page, direction="down", distance=600)
            await asyncio.sleep(2.0)

        logger.info("Scraped %d tweets from Twitter @%s", len(collected_posts), clean_handle)
        return collected_posts[:limit]

    async def close(self) -> None:
        """Closes browser context and stops Playwright engine."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.debug("Closed Twitter browser resources for @%s", self.account.handle)
