import json
import logging
import shutil
from pathlib import Path
from uuid import UUID

from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

DEFAULT_SESSIONS_DIR = Path("storage/browser_sessions")


class BrowserSessionManager:
    """
    Handles storage and validation of persistent Playwright sessions
    (cookies, tokens, and browser profiles) scoped per ConnectedAccount.
    """

    def __init__(self, base_dir: Path | str = DEFAULT_SESSIONS_DIR):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_account_session_dir(self, account_id: UUID | str) -> Path:
        """Returns the isolated Chrome profile directory for an account."""
        account_dir = self.base_dir / str(account_id)
        account_dir.mkdir(parents=True, exist_ok=True)
        return account_dir

    def get_storage_state_path(self, account_id: UUID | str) -> Path:
        """Returns the path to storage_state.json holding dumped cookies."""
        return self.get_account_session_dir(account_id) / "storage_state.json"

    def has_stored_session(self, account_id: UUID | str) -> bool:
        """Checks if a valid storage_state.json exists for the account."""
        state_file = self.get_storage_state_path(account_id)
        if not state_file.exists() or state_file.stat().st_size == 0:
            return False

        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("cookies"))
        except Exception as exc:
            logger.warning("Corrupted storage state for account %s: %s", account_id, exc)
            return False

    async def save_session_state(
        self, context: BrowserContext, account_id: UUID | str
    ) -> Path:
        """Dumps current cookies and local storage to storage_state.json."""
        target_path = self.get_storage_state_path(account_id)
        await context.storage_state(path=str(target_path))
        logger.debug("Saved browser session state to %s", target_path)
        return target_path

    def clear_account_session(self, account_id: UUID | str) -> None:
        """Deletes the stored Chrome profile and cookies for an account."""
        account_dir = self.base_dir / str(account_id)
        if account_dir.exists():
            shutil.rmtree(account_dir, ignore_errors=True)
            logger.info("Cleared browser session directory for account %s", account_id)
