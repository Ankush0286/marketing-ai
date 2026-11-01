import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.platforms.browser.session_manager import BrowserSessionManager


def test_session_manager_directories(tmp_path: Path):
    manager = BrowserSessionManager(base_dir=tmp_path)
    account_id = uuid4()

    session_dir = manager.get_account_session_dir(account_id)
    state_path = manager.get_storage_state_path(account_id)

    assert session_dir.exists()
    assert session_dir == tmp_path / str(account_id)
    assert state_path == session_dir / "storage_state.json"


def test_has_stored_session_lifecycle(tmp_path: Path):
    manager = BrowserSessionManager(base_dir=tmp_path)
    account_id = uuid4()

    # 1. Initially no session
    assert manager.has_stored_session(account_id) is False

    # 2. Corrupt or empty file
    state_file = manager.get_storage_state_path(account_id)
    state_file.write_text("not-json", encoding="utf-8")
    assert manager.has_stored_session(account_id) is False

    # 3. Valid session with cookies
    valid_payload = {"cookies": [{"name": "sessionid", "value": "12345"}], "origins": []}
    state_file.write_text(json.dumps(valid_payload), encoding="utf-8")
    assert manager.has_stored_session(account_id) is True

    # 4. Clear session
    manager.clear_account_session(account_id)
    assert manager.has_stored_session(account_id) is False
    assert not state_file.exists()


@pytest.mark.anyio
async def test_save_session_state(tmp_path: Path):
    manager = BrowserSessionManager(base_dir=tmp_path)
    account_id = uuid4()

    mock_context = MagicMock()
    mock_context.storage_state = AsyncMock()

    saved_path = await manager.save_session_state(mock_context, account_id)
    assert saved_path == manager.get_storage_state_path(account_id)
    mock_context.storage_state.assert_called_once_with(path=str(saved_path))
