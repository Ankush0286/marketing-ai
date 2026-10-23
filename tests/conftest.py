from collections.abc import Generator
from pathlib import Path
import pytest
from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import Session, sessionmaker

import libsql
from app.common.base_models import AuditBase
from app.db.base import Base
from app.db.proxy import LibSqlProxyConnection


# Lightweight model defined strictly for testing Base and AuditBase
class SampleItem(AuditBase):
    __tablename__ = "test_sample_items"
    name = Column(String(50), nullable=False)


@pytest.fixture
def temp_db_file(tmp_path: Path) -> Path:
    """Provides a fresh isolated database file path per test run."""
    return tmp_path / "test_local.db"


@pytest.fixture
def test_engine(temp_db_file: Path):
    """Creates a SQLAlchemy engine using the LibSqlProxyConnection and test DB."""
    def _creator():
        raw_conn = libsql.connect(database=str(temp_db_file))
        return LibSqlProxyConnection(raw_conn)

    engine = create_engine(
        "sqlite://",
        creator=_creator,
        future=True,
    )

    # Create tables defined on Base (e.g., SampleItem)
    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Yields a database session and handles transaction rollback/close."""
    TestingSession = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()