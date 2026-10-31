from collections.abc import Generator

from sqlalchemy.orm import Session

from .session import session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Dependency helper for FastAPI endpoints."""
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
