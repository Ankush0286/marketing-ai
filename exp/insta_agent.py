import asyncio
from dataclasses import dataclass
import os
from typing import Literal
from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

load_dotenv()

# ================= CONFIGURATION =================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your-openrouter-api-key")
MODEL_NAME = "deepseek/deepseek-v4-flash-0731"

IG_USERNAME = "orlume51"
IG_PASSWORD = "PKM9Ey$YbLUkTUH2uXx!"  # Change your password after testing!
SESSION_DIR = "./session/ig_session"
# =================================================


@dataclass
class BrowserDeps:
    page: Page


# 1. Initialize Native OpenRouterProvider & OpenRouterModel
provider = OpenRouterProvider(api_key=OPENROUTER_API_KEY)
model = OpenRouterModel(MODEL_NAME, provider=provider)

# 2. Create the PydanticAI Agent
instagram_agent = Agent(
    model,
    deps_type=BrowserDeps,
    system_prompt=(
        "You are an autonomous Instagram Browser Agent. "
        "You interact with the browser strictly by reading the distilled text UI state and calling tools.\n\n"
        "RULES:\n"
        "1. Always start by calling `observe_screen` to see what is currently on the page.\n"
        f"2. If you see a login screen, log in using username '{IG_USERNAME}' and password '{IG_PASSWORD}'.\n"
        "3. Dismiss popups like 'Allow all cookies', 'Save your login info?' (click 'Not now'), or 'Turn on Notifications' (click 'Not Now') if they appear.\n"
        "4. When searching for a user, click Search, use `type_text` on the Search input, wait for results to appear in the UI list, and click the matching profile link.\n"
        "5. To send a DM from a user's profile, click the 'Message' button, wait for the chat box to load, and use `type_text` with `press_enter=True` on the Message textbox.\n"
        "6. When uploading a file for a new post, call `upload_file` with the 'Select from computer' button's ID and the file path.\n"
        "7. Elements marked [IN MODAL] are inside an active popup/dialog—prioritize interacting with them when a modal is open."
    ),
)


# ================= DOM DISTILLATION ENGINE =================
async def get_distilled_ui(page: Page) -> str:
    """Scans the visible DOM, tags interactive elements with `data-agent-id`,

    and combines them with Playwright's semantic ARIA snapshot.
    """
    js_extract_interactive = """
    () => {
        document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));

        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return false;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) return false;
            return rect.bottom > 0 && rect.right > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth;
        };

        // Capture clickable parents of SVGs with aria-labels (Like, Search, New post, Direct, etc.)
        const svgParents = new Set();
        document.querySelectorAll('svg[aria-label]').forEach(svg => {
            const clickable = svg.closest('button, a, [role="button"], [role="link"]') || svg.parentElement;
            if (clickable) svgParents.add(clickable);
        });

        const selectors = [
            'a[href]', 'button', 'input', 'textarea', 'select',
            '[role="button"]', '[role="link"]', '[role="textbox"]',
            '[role="menuitem"]', '[role="tab"]', '[role="switch"]',
            '[role="checkbox"]', '[contenteditable="true"]'
        ].join(',');

        const candidates = new Set([...document.querySelectorAll(selectors), ...svgParents]);
        let idCounter = 1;
        let lines = [];

        for (const el of candidates) {
            if (!isVisible(el)) continue;

            // Prioritize aria-label, placeholder, and innerText BEFORE child SVG labels
            // so verified accounts in search results don't just get labeled "Verified"
            let label = (
                el.getAttribute('aria-label') ||
                el.getAttribute('placeholder') ||
                el.innerText ||
                el.querySelector('svg[aria-label]')?.getAttribute('aria-label') ||
                el.querySelector('img[alt]')?.getAttribute('alt') ||
                ''
            ).replace(/\\s+/g, ' ').trim();

            const tag = el.tagName.toLowerCase();
            const role = el.getAttribute('role') || tag;
            const typeAttr = el.getAttribute('type') ? ` type="${el.getAttribute('type')}"` : '';
            const hrefAttr = el.getAttribute('href') ? ` href="${el.getAttribute('href')}"` : '';
            const inModal = el.closest('[role="dialog"]') ? '[IN MODAL] ' : '';

            if (!label && !['input', 'textarea'].includes(tag) && role !== 'textbox') continue;

            el.setAttribute('data-agent-id', idCounter);
            lines.push(`[${idCounter}] ${inModal}<${role}${typeAttr}${hrefAttr}> "${label.slice(0, 90)}"`);
            idCounter++;
        }

        return lines.join('\\n');
    }
    """
    try:
        interactive_list = await page.evaluate(js_extract_interactive)
    except Exception as e:
        interactive_list = f"(Error reading interactive elements: {e})"

    # Grab semantic ARIA snapshot
    try:
        dialog = page.get_by_role("dialog").first
        if await dialog.is_visible():
            aria_tree = await dialog.aria_snapshot()
        else:
            aria_tree = await page.locator("body").aria_snapshot()
        aria_lines = "\n".join(aria_tree.splitlines()[:60])
    except Exception:
        aria_lines = "(ARIA snapshot unavailable)"

    return (
        f"CURRENT URL: {page.url}\n\n"
        f"=== INTERACTIVE ELEMENTS (Pass the [ID] number to tools) ===\n"
        f"{interactive_list or '(No interactive elements visible)'}\n\n"
        f"=== SEMANTIC TEXT / ARIA CONTEXT ===\n"
        f"{aria_lines}"
    )


# ================= AGENT TOOLS =================
@instagram_agent.tool
async def observe_screen(ctx: RunContext[BrowserDeps]) -> str:
    """Reads the current visible UI elements and text on the screen."""
    print("👀 [Agent] Observing screen...")
    await asyncio.sleep(1)
    return await get_distilled_ui(ctx.deps.page)


@instagram_agent.tool
async def click_element(
    ctx: RunContext[BrowserDeps], agent_id: int, description: str
) -> str:
    """Clicks an interactive element by its `[agent_id]` number."""
    print(f"🖱️ [Agent] Clicking [{agent_id}] ({description})...")
    page = ctx.deps.page
    target = page.locator(f'[data-agent-id="{agent_id}"]').first

    try:
        try:
            await target.click(timeout=4000)
        except Exception:
            await target.click(force=True, timeout=4000)
        await asyncio.sleep(2.5)
        return await get_distilled_ui(page)
    except Exception as e:
        return f"ERROR clicking [{agent_id}]: {e}\n\n" + await get_distilled_ui(
            page
        )


@instagram_agent.tool
async def type_text(
    ctx: RunContext[BrowserDeps],
    agent_id: int,
    text: str,
    press_enter: bool = False,
) -> str:
    """Types text into an input or textbox element identified by `[agent_id]`."""
    print(
        f"⌨️ [Agent] Typing '{text}' into [{agent_id}] (press_enter={press_enter})..."
    )
    page = ctx.deps.page
    target = page.locator(f'[data-agent-id="{agent_id}"]').first

    try:
        tag = await target.evaluate(
            "el => el.tagName.toLowerCase()", timeout=4000
        )

        # Click or force-click if an overlay (like Instagram's Search button overlay) intercepts pointer events
        try:
            await target.click(timeout=2500)
        except Exception:
            await target.click(force=True, timeout=2500)
            await target.evaluate("el => el.focus()")

        await asyncio.sleep(0.4)

        if tag in ("input", "textarea"):
            await target.fill(text, force=True)
        else:
            # Works reliably with Instagram's rich-text Lexical editors (DMs, Captions, Comments)
            await page.keyboard.insert_text(text)

        if press_enter:
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

        await asyncio.sleep(3)
        return await get_distilled_ui(page)
    except Exception as e:
        return (
            f"ERROR typing into [{agent_id}]: {e}\n\n"
            + await get_distilled_ui(page)
        )


@instagram_agent.tool
async def upload_file(
    ctx: RunContext[BrowserDeps], agent_id: int, file_path: str
) -> str:
    """Clicks a file-upload button (e.g., 'Select from computer') by `[agent_id]` and uploads `file_path`."""
    abs_path = os.path.abspath(file_path)
    print(f"📁 [Agent] Uploading '{abs_path}' via button [{agent_id}]...")
    if not os.path.exists(abs_path):
        return f"ERROR: File does not exist at {abs_path}"

    page = ctx.deps.page
    target = page.locator(f'[data-agent-id="{agent_id}"]').first

    try:
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            try:
                await target.click(timeout=4000)
            except Exception:
                await target.click(force=True, timeout=4000)

        file_chooser = await fc_info.value
        await file_chooser.set_files(abs_path)
        await asyncio.sleep(3)
        return await get_distilled_ui(page)
    except Exception as e:
        return (
            f"ERROR uploading file on [{agent_id}]: {e}\n\n"
            + await get_distilled_ui(page)
        )


@instagram_agent.tool
async def scroll_page(
    ctx: RunContext[BrowserDeps],
    direction: Literal["down", "up"] = "down",
    amount: int = 600,
) -> str:
    """Scrolls the page up or down to reveal more posts or elements."""
    print(f"📜 [Agent] Scrolling {direction}...")
    page = ctx.deps.page
    delta = amount if direction == "down" else -amount
    await page.mouse.wheel(0, delta)
    await asyncio.sleep(2)
    return await get_distilled_ui(page)


@instagram_agent.tool
async def navigate_to(ctx: RunContext[BrowserDeps], url: str) -> str:
    """Navigates the browser directly to a specific URL."""
    print(f"🌐 [Agent] Navigating to {url}...")
    page = ctx.deps.page
    try:
        await page.goto(url)
        await asyncio.sleep(4)
    except Exception as e:
        return f"ERROR navigating to {url}: {e}\n\n" + await get_distilled_ui(
            page
        )
    return await get_distilled_ui(page)


@instagram_agent.tool
async def wait_seconds(ctx: RunContext[BrowserDeps], seconds: int = 4) -> str:
    """Waits for a specified number of seconds."""
    print(f"⏳ [Agent] Waiting {seconds}s...")
    await asyncio.sleep(min(seconds, 15))
    return await get_distilled_ui(ctx.deps.page)


# ================= MAIN RUNNER =================
async def run_instagram_task(task_prompt: str):
    async with async_playwright() as p:
        print("Launching headed Chrome...")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )

        page = browser.pages[0]
        await page.goto("https://www.instagram.com/")
        await asyncio.sleep(4)

        deps = BrowserDeps(page=page)

        print(f"\n🤖 Starting Agent with task:\n👉 {task_prompt}\n")
        result = await instagram_agent.run(task_prompt, deps=deps)

        print("\n✅ Agent Finished! Final Response:")
        print(result.output)

        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    PROMPT = "Find a AI influencer and send a dm saying hi to him"
    asyncio.run(run_instagram_task(PROMPT))