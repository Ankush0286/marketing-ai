from unittest.mock import MagicMock

import pytest

from app.common.enums import PlatformType
from app.modules.accounts.models import ConnectedAccount
from app.platforms.base import BasePlatformAdapter, PublishResult, ScrapedPost
from app.platforms.instagram.adapter import InstagramAdapter
from app.platforms.registry import PlatformRegistry, UnsupportedPlatformError
from app.platforms.twitter.adapter import TwitterAdapter


class DummyFacebookAdapter(BasePlatformAdapter):
    """Mock adapter for registry tests."""

    async def authenticate(self) -> bool:
        return True

    async def publish_post(self, content: str, media_paths: list[str] | None = None) -> PublishResult:
        _ = (content, media_paths)
        return PublishResult(platform_post_id="dummy_123")

    async def send_dm(self, recipient_handle: str, message_text: str) -> str:
        _ = (recipient_handle, message_text)
        return "dm_123"

    async def scrape_feed(self, target_handle: str, limit: int = 15) -> list[ScrapedPost]:
        _ = (target_handle, limit)
        return []

    async def close(self) -> None:
        pass


def test_registry_resolves_built_in_adapters():
    # Instagram
    assert PlatformRegistry.is_supported(PlatformType.INSTAGRAM) is True
    mock_ig = MagicMock(spec=ConnectedAccount)
    mock_ig.platform = PlatformType.INSTAGRAM
    mock_ig.id = MagicMock()
    assert isinstance(PlatformRegistry.get_adapter(mock_ig), InstagramAdapter)

    # Twitter
    assert PlatformRegistry.is_supported(PlatformType.TWITTER) is True
    mock_tw = MagicMock(spec=ConnectedAccount)
    mock_tw.platform = PlatformType.TWITTER
    mock_tw.id = MagicMock()
    assert isinstance(PlatformRegistry.get_adapter(mock_tw), TwitterAdapter)


def test_registry_unsupported_platform_raises():
    mock_account = MagicMock(spec=ConnectedAccount)
    mock_account.platform = PlatformType.EMAIL

    with pytest.raises(UnsupportedPlatformError):
        PlatformRegistry.get_adapter(mock_account)


def test_register_custom_adapter():
    PlatformRegistry.register(PlatformType.FACEBOOK, DummyFacebookAdapter)
    assert PlatformRegistry.is_supported(PlatformType.FACEBOOK) is True

    mock_account = MagicMock(spec=ConnectedAccount)
    mock_account.platform = PlatformType.FACEBOOK

    adapter = PlatformRegistry.get_adapter(mock_account)
    assert isinstance(adapter, DummyFacebookAdapter)
