import logging
from typing import Any

logger = logging.getLogger(__name__)


class LibSqlProxyCursor:
    """
    Proxy wrapper around a libSQL cursor to ensure full PEP 249 compatibility
    and graceful attribute fallbacks for SQLAlchemy introspection.
    """

    def __init__(self, raw_cursor: Any, proxy_conn: "LibSqlProxyConnection"):
        self._cursor = raw_cursor
        self._proxy_conn = proxy_conn

    @property
    def connection(self) -> "LibSqlProxyConnection":
        """SQLAlchemy occasionally references cursor.connection to verify dialect state."""
        return self._proxy_conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class LibSqlProxyConnection:
    """
    Proxy wrapper around a native libSQL / Turso connection.

    1. Intercepts SQLAlchemy's dialect initialization call to `create_function`.
    2. Exposes `.sync()` so the application can manually sync the local embedded replica.
    3. Forwards all queries, transactions, and cursors to the underlying libSQL C/Rust extension.
    """

    def __init__(self, raw_connection: Any):
        self._conn = raw_connection

    def create_function(
        self,
        name: str,
        num_params: int,
        func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Intercepts SQLite function creation from SQLAlchemy.
        libSQL does not support dynamic Python-side function registration.
        """
        logger.debug("Intercepted unsupported SQLite create_function: %s", name)
        return None

    def cursor(self, *args: Any, **kwargs: Any) -> LibSqlProxyCursor:
        """Returns a wrapped cursor pointing back to this proxy connection."""
        raw_cursor = self._conn.cursor(*args, **kwargs)
        return LibSqlProxyCursor(raw_cursor, self)

    def sync(self) -> None:
        """
        Pushes local writes from local_auth.db to Turso Cloud
        and pulls latest upstream changes down to disk.
        """
        if hasattr(self._conn, "sync"):
            self._conn.sync()
            logger.debug("Turso embedded replica successfully synced with cloud.")
        else:
            logger.warning("libSQL connection does not support sync (running offline/local mode).")

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        """Fallback to delegate any other DBAPI attributes (e.g. isolation_level, in_transaction)."""
        return getattr(self._conn, name)