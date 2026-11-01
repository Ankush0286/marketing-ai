from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.common.enums import PlatformType
from app.modules.accounts.models import ConnectedAccount
from app.platforms.browser.session_manager import BrowserSessionManager
from app.platforms.twitter.adapter import TwitterAdapter


@pytest.mark.anyio
async def test_publish_post_validates_media_files(tmp_path: Path):
    mock_account = MagicMock(spec=ConnectedAccount)
    mock_account.id = uuid4()
    mock_account.platform = PlatformType.TWITTER

    adapter = TwitterAdapter(
        account=mock_account,
        session_manager=BrowserSessionManager(base_dir=tmp_path),
    )

    # File does not exist on disk -> raises FileNotFoundError immediately
    fake_file = tmp_path / "missing_tweet_image.png"
    with pytest.raises(FileNotFoundError):
        await adapter.publish_post("Tweet with missing image", media_paths=[str(fake_file)])


@pytest.mark.anyio
async def test_adapter_close_teardown(tmp_path: Path):
    mock_account = MagicMock(spec=ConnectedAccount)
    mock_account.id = uuid4()
    mock_account.platform = PlatformType.TWITTER

    adapter = TwitterAdapter(
        account=mock_account,
        session_manager=BrowserSessionManager(base_dir=tmp_path),
    )

    # Mock active browser context and playwright instance
    mock_context = MagicMock()
    mock_context.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.stop = AsyncMock()

    adapter._context = mock_context
    adapter._playwright = mock_playwright

    # Teardown should cleanly close both
    await adapter.close()

    mock_context.close.assert_called_once()
    mock_playwright.stop.assert_called_once()
    assert adapter._context is None
    assert adapter._playwright is None
