from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import _ensure_local_db_dir, get_db_session


def test_ensure_local_db_dir_creates_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify parent directories for LOCAL_DB_PATH are created if missing."""
    nested_path = tmp_path / "deep" / "dir" / "test.db"

    from app.core import config
    monkeypatch.setattr(config.settings, "LOCAL_DB_PATH", str(nested_path))

    ensured = _ensure_local_db_dir()

    assert ensured.parent.exists()
    assert ensured == nested_path.resolve()


def test_get_db_session_lifecycle():
    """Verify get_db_session yields an active session and closes upon iteration completion."""
    session_gen = get_db_session()
    session = next(session_gen)

    assert isinstance(session, Session)
    assert session.is_active

    with pytest.raises(StopIteration):
        next(session_gen)


def test_session_rollback_on_error(db_session: Session):
    """Verify transactional safety: rolled back data is never committed."""
    db_session.execute(text("CREATE TABLE temp_log (id INT, msg TEXT);"))
    db_session.commit()

    try:
        db_session.execute(text("INSERT INTO temp_log VALUES (1, 'initial');"))
        raise ValueError("Simulated unexpected crash")
    except ValueError:
        db_session.rollback()

    # The uncommitted row must not exist
    count = db_session.execute(text("SELECT COUNT(*) FROM temp_log;")).scalar()
    assert count == 0
