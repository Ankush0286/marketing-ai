import logging
from pathlib import Path
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
)

logger = logging.getLogger(__name__)

# Modern Chrome desktop user-agent
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# Common Chrome command line arguments to strip automation fingerprints
STEALTH_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-features=TranslateUI,BlinkGenPropertyTrees",
    "--no-default-browser-check",
    "--no-first-run",
    "--start-maximized",
]

# Client-side JavaScript evaluated on every new document to defeat bot heuristics
STEALTH_INIT_SCRIPT = """
(() => {
    // 1. Mask navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Spoof Chrome runtime object
    window.chrome = {
        app: { isInstalled: false },
        runtime: {},
        loadTimes: () => ({}),
        csi: () => ({})
    };

    // 3. Spoof Plugins list (never empty on real desktop browsers)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
        configurable: true
    });

    // 4. Spoof Languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
    });

    // 5. Mock Permissions API query
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
})();
"""


async def apply_stealth_to_page(page: Page) -> None:
    """Applies client-side evasions to a single page."""
    await page.add_init_script(STEALTH_INIT_SCRIPT)


async def create_stealth_context(
    playwright: Playwright,
    user_data_dir: Path | str,
    headless: bool = True,
    storage_state_path: Path | str | None = None,
    **kwargs: Any,
) -> BrowserContext:
    """
    Creates a persistent Chrome browser context hardened against bot detection.
    Persists cookies, indexedDB, and local storage inside user_data_dir.
    """
    user_data_path = Path(user_data_dir).resolve()
    user_data_path.mkdir(parents=True, exist_ok=True)

    context_kwargs: dict[str, Any] = {
        "user_data_dir": str(user_data_path),
        "channel": "chromium",
        "headless": headless,
        "args": STEALTH_ARGS,
        "user_agent": DEFAULT_USER_AGENT,
        "viewport": None,  # Match native window / maximized
        "no_viewport": True,
        "ignore_https_errors": True,
        **kwargs,
    }

    if storage_state_path and Path(storage_state_path).exists():
        context_kwargs["storage_state"] = str(storage_state_path)

    logger.debug("Launching stealth persistent context at %s (headless=%s)", user_data_path, headless)
    context = await playwright.chromium.launch_persistent_context(**context_kwargs)

    # Automatically apply stealth script to all current and future tabs/pages
    await context.add_init_script(STEALTH_INIT_SCRIPT)
    for existing_page in context.pages:
        await apply_stealth_to_page(existing_page)

    return context
