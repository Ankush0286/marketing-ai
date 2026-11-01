from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.modules.accounts.models import ConnectedAccount


@dataclass(frozen=True)
class PublishResult:
    """Standardized response from platform adapters after posting."""

    platform_post_id: str
    platform_post_url: str | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScrapedPost:
    """Standardized representation of an intercepted or scraped post."""

    platform_post_id: str
    author_handle: str
    content: str
    platform_post_url: str | None = None
    published_at: datetime | None = None
    like_count: int | None = None
    reply_count: int | None = None
    extra_metadata: dict[str, Any] | None = None


class BasePlatformAdapter(ABC):
    """
    Abstract interface that all social media automation adapters must implement
    (Twitter, Instagram, Facebook, etc.).
    """

    def __init__(self, account: ConnectedAccount):
        self.account = account

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Verifies whether the account has a valid authenticated session
        (via stored cookies, API tokens, or headless browser session).
        """
        raise NotImplementedError

    @abstractmethod
    async def publish_post(
        self,
        content: str,
        media_paths: list[str] | None = None,
    ) -> PublishResult:
        """Publishes a text or media post to the target platform."""
        _ = (content, media_paths)
        raise NotImplementedError

    @abstractmethod
    async def send_dm(
        self,
        recipient_handle: str,
        message_text: str,
    ) -> str:
        """Sends a private direct message to an account and returns the message ID."""
        _ = (recipient_handle, message_text)
        raise NotImplementedError

    @abstractmethod
    async def scrape_feed(
        self,
        target_handle: str,
        limit: int = 15,
    ) -> list[ScrapedPost]:
        """Scrapes the most recent posts from a specific competitor or watched profile."""
        _ = (target_handle, limit)
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Cleans up active browser contexts, sockets, or HTTP client sessions."""
        raise NotImplementedError
    