from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import pytest
from playwright.async_api import async_playwright

from app.platforms.browser.driver import create_stealth_context
from app.platforms.browser.human_behavior import human_scroll, human_type
from app.platforms.browser.session_manager import BrowserSessionManager


@pytest.mark.anyio
async def test_stealth_driver_and_human_behavior_e2e(tmp_path: Path):
    """
    Integration test launching a real Chromium browser instance to verify:
    1. Stealth evasions defeat navigator.webdriver detection inside the browser.
    2. human_type() accurately types into real interactive HTML elements.
    3. human_scroll() dispatches genuine mouse wheel events.
    4. BrowserSessionManager dumps real cookies and storage state to disk.
    """
    account_id = uuid4()
    session_mgr = BrowserSessionManager(base_dir=tmp_path / "sessions")
    user_data_dir = session_mgr.get_account_session_dir(account_id)

    async with async_playwright() as playwright:
        context = await create_stealth_context(
            playwright=playwright,
            user_data_dir=user_data_dir,
            headless=True,
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Serve test sandbox through a real browser navigation target
        test_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Automation Test Sandbox</title></head>
        <body style="height: 3000px; padding: 20px;">
            <h1>Stealth Test Page</h1>
            <input id="sample-input" type="text" placeholder="Type here..." />
            <textarea id="sample-textarea"></textarea>
        </body>
        </html>
        """
        await page.goto(f"data:text/html;charset=utf-8,{quote(test_html)}")

        # -------------------------------------------------------------
        # 1. Verify Stealth Evasions inside real JavaScript context
        # -------------------------------------------------------------
        is_webdriver = await page.evaluate("navigator.webdriver")
        assert is_webdriver in (False, None)  # Successfully masked from True

        has_chrome_obj = await page.evaluate("Boolean(window.chrome && window.chrome.runtime)")
        assert has_chrome_obj is True  # Spoofed Chrome runtime object present

        plugins_length = await page.evaluate("navigator.plugins.length")
        assert plugins_length > 0  # Desktop browser must have plugins

        # -------------------------------------------------------------
        # 2. Verify human_type() on real DOM input
        # -------------------------------------------------------------
        input_locator = page.locator("#sample-input")
        test_text = "Automated Marketing Post #AI"

        # Use micro-delays for fast integration test execution
        await human_type(page, input_locator, test_text, min_delay_ms=5, max_delay_ms=15)
        entered_value = await input_locator.input_value()
        assert entered_value == test_text

        # -------------------------------------------------------------
        # 3. Verify human_scroll() on real scrollable viewport
        # -------------------------------------------------------------
        initial_scroll_y = await page.evaluate("window.scrollY")
        assert initial_scroll_y == 0

        await human_scroll(page, direction="down", distance=400, steps=3)
        scrolled_y = await page.evaluate("window.scrollY")
        assert scrolled_y > 0

        # -------------------------------------------------------------
        # 4. Verify cookie persistence & session saving
        # -------------------------------------------------------------
        await context.add_cookies([
            {
                "name": "test_auth_token",
                "value": "secret_session_cookie_xyz",
                "domain": "localhost",
                "path": "/",
            }
        ])

        saved_path = await session_mgr.save_session_state(context, account_id)
        assert saved_path.exists()
        assert session_mgr.has_stored_session(account_id) is True

        await context.close()
