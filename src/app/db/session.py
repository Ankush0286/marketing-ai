import libsql
import logging
from typing import Any
from pathlib import Path
from sqlalchemy import create_engine
from collections.abc import Generator
from sqlalchemy.orm import Session, sessionmaker

from .proxy import LibSqlProxyConnection
from app.core.config import settings

logger = logging.getLogger(__name__)

def _ensure_local_db_dir() -> Path:
    """
    Ensures the parent directory for the local SQLite embedded replica exists
    before libSQL attempts to open or initialize the file.
    """
    db_path = Path(settings.LOCAL_DB_PATH).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _create_libsql_connection() -> LibSqlProxyConnection:
    """
    Establishes an embedded replica connection using libSQL:
    - Reads and writes locally to disk (LOCAL_DB_PATH) with microsecond latency.
    - Synchronizes changes with Turso Cloud when sync_url and auth_token are configured.
    - Wraps the raw connection in LibSqlProxyConnection to bypass SQLAlchemy's
      create_function dialect checks.
    """
    db_path = _ensure_local_db_dir()

    # Embedded replica mode (local file synced to Turso Cloud)
    if settings.TURSO_DATABASE_URL and settings.TURSO_AUTH_TOKEN:
        logger.debug("Connecting to Turso embedded replica at %s", db_path)
        raw_conn: Any = libsql.connect(
            database=str(db_path),
            sync_url=settings.TURSO_DATABASE_URL,
            auth_token=settings.TURSO_AUTH_TOKEN,
        )

        # Trigger initial sync on startup to pull the latest schema/data
        try:
            raw_conn.sync()
            logger.info("Turso embedded replica initialized and synced with cloud.")
        except Exception as exc:
            # Allow startup to continue in offline-first mode if internet/remote is unreachable
            logger.warning(
                "Initial Turso cloud sync failed (falling back to offline local DB): %s",
                exc,
            )
    else:
        # Local-only standalone SQLite mode (useful for offline dev/tests)
        logger.info("Connecting to local standalone libSQL database at %s", db_path)
        raw_conn = libsql.connect(database=str(db_path))

    return LibSqlProxyConnection(raw_conn)


# SQLAlchemy 2.0 Engine
# sqlite:// tells SQLAlchemy to treat this as SQLite syntax,
# while the creator hook supplies our proxy-wrapped libSQL connection.
engine = create_engine(
    "sqlite://",
    creator=_create_libsql_connection,
    echo=settings.DB_ECHO,
    future=True,
)

# Global Session Factory
session_factory: sessionmaker[Session] = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request,
    rolling back transactions on error and closing the session on completion.
    """
    session: Session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sync_replica() -> None:
    """
    Manually triggers synchronization between the local embedded replica and Turso Cloud.
    Can be called by background schedulers, watcher loops, or API endpoints after writes.
    """
    try:
        with engine.connect() as conn:
            # Access underlying DBAPI connection through SQLAlchemy's raw connection
            dbapi_conn = conn.connection.dbapi_connection
            if hasattr(dbapi_conn, "sync"):
                dbapi_conn.sync()
                logger.info("Turso replica sync completed successfully.")
            else:
                logger.warning("Active DBAPI connection does not support sync.")
    except Exception as exc:
        logger.error("Failed to sync Turso replica to cloud: %s", exc)
        raise
