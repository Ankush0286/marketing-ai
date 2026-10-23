from unittest.mock import MagicMock
from app.db.proxy import LibSqlProxyConnection, LibSqlProxyCursor


def test_proxy_intercepts_create_function():
    """Verify create_function does not throw errors on native libSQL."""
    mock_raw_conn = MagicMock()
    proxy = LibSqlProxyConnection(mock_raw_conn)

    # SQLAlchemy calls this during SQLite initialization
    result = proxy.create_function("custom_func", 1, lambda x: x)

    assert result is None
    # Verify it was not forwarded as an invalid call to the underlying driver
    assert not hasattr(mock_raw_conn, "create_function") or not mock_raw_conn.create_function.called


def test_proxy_delegates_transaction_methods():
    """Verify commit, rollback, and close calls forward to raw connection."""
    mock_raw_conn = MagicMock()
    proxy = LibSqlProxyConnection(mock_raw_conn)

    proxy.commit()
    mock_raw_conn.commit.assert_called_once()

    proxy.rollback()
    mock_raw_conn.rollback.assert_called_once()

    proxy.close()
    mock_raw_conn.close.assert_called_once()


def test_proxy_cursor_wraps_correctly():
    """Verify cursor() wraps raw cursor and maintains connection reference."""
    mock_raw_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_raw_conn.cursor.return_value = mock_cursor

    proxy = LibSqlProxyConnection(mock_raw_conn)
    cursor = proxy.cursor()

    assert isinstance(cursor, LibSqlProxyCursor)
    assert cursor.connection is proxy


def test_proxy_sync_delegation():
    """Verify sync() is called on the underlying libSQL connection if available."""
    mock_raw_conn = MagicMock()
    mock_raw_conn.sync = MagicMock()

    proxy = LibSqlProxyConnection(mock_raw_conn)
    proxy.sync()

    mock_raw_conn.sync.assert_called_once()