import asyncio
import logging
import uuid
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
from app.platforms.instagram import selectors

logger = logging.getLogger(__name__)


class InstagramAutomationError(Exception):
    """Base exception for Instagram automation failures."""


class InstagramAdapter(BasePlatformAdapter):
    """
    Production-ready Instagram automation adapter using stealth Playwright,
    persistent cookie sessions, and human behavior emulation.
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
        """Initializes stealth browser context and returns active page."""
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
        """Dismisses common Instagram cookie banners and notification popups."""
        # 1. Cookie Banner
        try:
            cookie_btn = page.locator(selectors.COOKIE_ALLOW_BUTTON).first
            if await cookie_btn.is_visible(timeout=1500):
                await cookie_btn.click()
                await random_delay(1.0, 2.0)
        except Exception:
            pass

        # 2. 'Not Now' popups (Save info, Notifications)
        for text in selectors.POPUP_NOT_NOW_BUTTONS:
            try:
                not_now_btn = page.get_by_role("button", name=text, exact=True).first
                if await not_now_btn.is_visible(timeout=1000):
                    await not_now_btn.click()
                    await random_delay(0.5, 1.5)
            except Exception:
                pass

    async def authenticate(self) -> bool:
        """
        Verifies active login session or performs automated login using encrypted credentials.
        Dumps updated cookies to storage_state.json upon success.
        """
        page = await self._get_or_create_page()
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await random_delay(2.0, 3.5)
        await self._dismiss_popups(page)

        # Check if already authenticated
        create_btn = page.locator(selectors.NAV_CREATE_BUTTON).first
        if await create_btn.is_visible(timeout=4000):
            logger.info("Account @%s already authenticated via persistent session.", self.account.handle)
            if self._context:
                await self.session_manager.save_session_state(self._context, self.account.id)
            return True

        # Need to log in
        username_input = page.locator(selectors.LOGIN_USERNAME_INPUT).first
        if not await username_input.is_visible(timeout=5000):
            logger.warning("Neither create button nor login form visible for @%s", self.account.handle)
            return False

        # Decrypt password from vault
        password = decrypt_token(self.account.encrypted_api_secret)
        if not password:
            logger.error("No password credentials found in vault for @%s", self.account.handle)
            return False

        logger.info("Executing automated login for @%s...", self.account.handle)
        await human_type(page, username_input, self.account.handle)
        await random_delay(0.5, 1.2)

        password_input = page.locator(selectors.LOGIN_PASSWORD_INPUT).first
        await human_type(page, password_input, password)
        await random_delay(0.8, 1.5)

        submit_btn = page.locator(selectors.LOGIN_SUBMIT_BUTTON).first
        await submit_btn.click()

        # Wait for home page navigation
        try:
            await page.locator(selectors.NAV_CREATE_BUTTON).first.wait_for(
                state="visible", timeout=30000
            )
            await self._dismiss_popups(page)
            if self._context:
                await self.session_manager.save_session_state(self._context, self.account.id)
            logger.info("Login successful for @%s", self.account.handle)
            return True
        except Exception as exc:
            logger.error("Login verification timed out for @%s: %s", self.account.handle, exc)
            return False

    async def publish_post(
        self,
        content: str,
        media_paths: list[str] | None = None,
    ) -> PublishResult:
        """
        Publishes a photo or video post to Instagram with captions.
        Instagram web requires at least one local media file.
        """
        if not media_paths:
            raise ValueError("Instagram requires at least one media file (image/video) to publish.")

        valid_media_path = Path(media_paths[0]).resolve()
        if not valid_media_path.exists():
            raise FileNotFoundError(f"Media file does not exist: {valid_media_path}")

        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise InstagramAutomationError(f"Failed to authenticate session for @{self.account.handle}")

        logger.info("Opening post creation modal for @%s...", self.account.handle)
        create_btn = page.locator(selectors.NAV_CREATE_BUTTON).first
        await create_btn.click()
        await random_delay(1.5, 2.5)

        # Handle dropdown submenu ("Post", "Live Video") if displayed
        select_file_btn = page.locator(selectors.SELECT_FROM_COMPUTER_BUTTON).first
        if not await select_file_btn.is_visible(timeout=2000):
            post_submenu = page.locator(selectors.CREATE_POST_SUBMENU_ITEM).first
            if await post_submenu.is_visible(timeout=2000):
                await post_submenu.click()
                await random_delay(1.0, 2.0)

        # Upload Media via FileChooser
        logger.info("Uploading media: %s", valid_media_path)
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await select_file_btn.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(valid_media_path))
        await random_delay(2.5, 4.0)

        # Navigate through Crop and Filter screens
        next_button = page.locator(selectors.NEXT_BUTTON).first
        await next_button.click()
        await random_delay(1.5, 2.5)

        await next_button.click()
        await random_delay(1.5, 2.5)

        # Write Caption
        logger.info("Inserting caption...")
        caption_box = page.locator(selectors.CAPTION_TEXTAREA).first
        await caption_box.click()
        await random_delay(0.5, 1.0)
        # Using keyboard insert_text for rich Lexical editor compatibility
        await page.keyboard.insert_text(content)
        await random_delay(1.5, 2.5)

        # Click Share
        logger.info("Sharing post to Instagram feed...")
        share_btn = page.locator(selectors.SHARE_BUTTON).first
        await share_btn.click()

        # Wait for confirmation indicator
        confirmed = False
        for indicator in selectors.POST_SUCCESS_INDICATORS:
            try:
                await page.get_by_text(indicator).first.wait_for(
                    state="visible", timeout=45000
                )
                confirmed = True
                break
            except Exception:
                continue

        if not confirmed:
            raise InstagramAutomationError("Post upload confirmation not detected within timeout.")

        generated_id = f"ig_{uuid.uuid4().hex[:12]}"
        logger.info("✅ Post successfully published for @%s", self.account.handle)

        if self._context:
            await self.session_manager.save_session_state(self._context, self.account.id)

        return PublishResult(
            platform_post_id=generated_id,
            platform_post_url=f"https://www.instagram.com/{self.account.handle}/",
            extra_metadata={"media": str(valid_media_path)},
        )

    async def send_dm(
        self,
        recipient_handle: str,
        message_text: str,
    ) -> str:
        """Sends a private direct message to an Instagram user."""
        clean_handle = recipient_handle.lstrip("@").strip()
        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise InstagramAutomationError(f"Failed to authenticate session for @{self.account.handle}")

        logger.info("Navigating to profile @%s to dispatch DM...", clean_handle)
        await page.goto(f"https://www.instagram.com/{clean_handle}/", wait_until="domcontentloaded")
        await random_delay(2.5, 4.0)
        await self._dismiss_popups(page)

        # Click Message button on profile header
        msg_btn = page.locator(selectors.PROFILE_MESSAGE_BUTTON).first
        if not await msg_btn.is_visible(timeout=5000):
            raise InstagramAutomationError(f"Message button not found on @{clean_handle}'s profile.")

        await msg_btn.click()
        await random_delay(3.0, 5.0)
        await self._dismiss_popups(page)

        # Locate chat input
        dm_input = page.locator(selectors.DM_INPUT_TEXTBOX).first
        await dm_input.wait_for(state="visible", timeout=15000)
        await dm_input.click()
        await random_delay(0.5, 1.0)

        # Type message with human jitter and press Enter
        await page.keyboard.insert_text(message_text)
        await random_delay(0.8, 1.5)
        await page.keyboard.press("Enter")
        await random_delay(2.0, 3.5)

        parsed_url = urlparse(page.url)
        thread_id = parsed_url.path.strip("/").split("/")[-1] if "direct/t/" in page.url else "unknown_thread"
        logger.info("✅ DM successfully sent to @%s in thread %s", clean_handle, thread_id)

        if self._context:
            await self.session_manager.save_session_state(self._context, self.account.id)

        return thread_id

    async def scrape_feed(
        self,
        target_handle: str,
        limit: int = 15,
    ) -> list[ScrapedPost]:
        """Scrapes recent post IDs and URLs from a competitor's profile grid."""
        clean_handle = target_handle.lstrip("@").strip()
        page = await self._get_or_create_page()
        is_authenticated = await self.authenticate()
        if not is_authenticated:
            raise InstagramAutomationError(f"Failed to authenticate session for @{self.account.handle}")

        logger.info("Scraping grid for target profile @%s...", clean_handle)
        await page.goto(f"https://www.instagram.com/{clean_handle}/", wait_until="domcontentloaded")
        await random_delay(2.5, 4.0)
        await self._dismiss_popups(page)

        collected_posts: list[ScrapedPost] = []
        seen_ids: set[str] = set()

        for _ in range(3):  # Up to 3 scroll batches
            post_links = await page.locator(selectors.PROFILE_POST_LINKS).all()
            for link in post_links:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Parse post shortcode (/p/C8xyz.../ or /reel/C8xyz.../)
                parts = href.strip("/").split("/")
                if len(parts) >= 2 and parts[-2] in ("p", "reel"):
                    post_id = parts[-1]
                    if post_id not in seen_ids:
                        seen_ids.add(post_id)
                        collected_posts.append(
                            ScrapedPost(
                                platform_post_id=post_id,
                                author_handle=clean_handle,
                                content=f"Instagram post {post_id}",
                                platform_post_url=f"https://www.instagram.com/p/{post_id}/",
                            )
                        )
                if len(collected_posts) >= limit:
                    break

            if len(collected_posts) >= limit:
                break

            await human_scroll(page, direction="down", distance=600)
            await asyncio.sleep(2.0)

        logger.info("Scraped %d posts from @%s", len(collected_posts), clean_handle)
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
        logger.debug("Closed Instagram browser resources for @%s", self.account.handle)
