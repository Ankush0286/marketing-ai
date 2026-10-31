import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Guarantee test environment variables are set before application settings load
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long-123456")

from app.common.base_models import AuditBase
from app.core.security import _get_fernet_cipher
from app.db import all_models  # noqa: F401 - ensures all domain models register with Base.metadata
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.main import app as fastapi_app

# =============================================================================
# Test-Only Models
# =============================================================================


class SampleItem(AuditBase, Base):
    """Concrete model inheriting from AuditBase for testing UUIDs and timestamps."""

    __tablename__ = "sample_items"
    __table_args__ = {"extend_existing": True}

    name = Column(String(100), nullable=True)


# =============================================================================
# Security & Cache Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_cipher_cache() -> Generator[None, None, None]:
    """Clears the lru_cache on the Fernet cipher before and after each test."""
    _get_fernet_cipher.cache_clear()
    yield
    _get_fernet_cipher.cache_clear()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_engine():
    """
    Creates a single in-memory SQLite engine shared across the test session.
    Uses StaticPool so all connections within a test share the same in-memory state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Provides an isolated transactional database session per test function.
    Automatically rolls back any committed or uncommitted changes upon exit,
    keeping every test completely isolated.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


# =============================================================================
# FastAPI Integration Client Fixture
# =============================================================================


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Provides a FastAPI TestClient with `get_db_session` overridden to use
    the isolated per-test `db_session`.
    """

    def _override_get_db_session() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db_session] = _override_get_db_session

    with TestClient(fastapi_app, raise_server_exceptions=False) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
