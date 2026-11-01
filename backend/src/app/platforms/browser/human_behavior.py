import asyncio
import logging
import random
from typing import Literal

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)


async def random_delay(min_seconds: float = 1.0, max_seconds: float = 2.5) -> None:
    """Asynchronously sleeps for a randomized organic duration."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def human_type(
    page: Page,
    target: Locator | str,
    text: str,
    min_delay_ms: int = 40,
    max_delay_ms: int = 120,
) -> None:
    """
    Types text into an element one character at a time with randomized
    inter-keystroke intervals and natural pauses after punctuation marks.
    """
    locator = page.locator(target) if isinstance(target, str) else target

    # Focus and clear if input or textarea
    await locator.click()
    await asyncio.sleep(random.uniform(0.2, 0.4))

    for char in text:
        # Punctuation pauses simulate cognitive reading/typing pauses
        if char in {".", ",", "!", "?", "\n"}:
            char_delay = random.uniform(0.3, 0.6)
            await page.keyboard.type(char)
            await asyncio.sleep(char_delay)
        else:
            jitter = random.randint(min_delay_ms, max_delay_ms) / 1000.0
            await page.keyboard.type(char, delay=jitter)

    await asyncio.sleep(random.uniform(0.3, 0.7))


async def human_scroll(
    page: Page,
    direction: Literal["down", "up"] = "down",
    distance: int = 500,
    steps: int = 5,
) -> None:
    """
    Simulates smooth, non-linear mouse wheel scrolling divided across
    micro-movements.
    """
    step_distance = distance // steps
    sign = 1 if direction == "down" else -1

    for _ in range(steps):
        # Slightly jitter each micro scroll step
        jittered_step = step_distance + random.randint(-15, 15)
        await page.mouse.wheel(0, sign * jittered_step)
        await asyncio.sleep(random.uniform(0.08, 0.22))

    await asyncio.sleep(random.uniform(0.5, 1.2))
