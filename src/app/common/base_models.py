from uuid import UUID, uuid4
from sqlalchemy import DateTime
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    """Mixin for UUID v4 primary keys."""

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        sort_order=-10,  # Keeps primary key at top of table definition
    )


class TimestampMixin:
    """Mixin for automatic timezone-aware audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        sort_order=99,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        sort_order=100,
    )


class AuditBase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Abstract base class providing UUID PK and created/updated timestamps.
    Inherit from this class for standard business entities.
    """

    __abstract__ = True
    