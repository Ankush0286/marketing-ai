from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_models import AuditBase
from app.common.enums import AccountStatus, AuthMethod, PlatformType


class ConnectedAccount(AuditBase):
    __tablename__ = "accounts"

    # --------------- Identity & Platform ---------------
    platform: Mapped[PlatformType] = mapped_column(
        SAEnum(PlatformType, native_enum=False),
        nullable=False,
        index=True,
    )
    handle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(150), 
        nullable=True
    )
    platform_user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # --------------- Status & Authentication Mode ---------------
    status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus, native_enum=False),
        default=AccountStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    auth_method: Mapped[AuthMethod] = mapped_column(
        SAEnum(AuthMethod, native_enum=False),
        default=AuthMethod.HYBRID,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )

    # --------------- Encrypted API Credential Vault ---------------
    # Encrypted via Fernet AES-128 before storage; decrypted only in-memory.
    encrypted_access_token: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    encrypted_refresh_token: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    encrypted_token_secret: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    encrypted_api_key: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    encrypted_api_secret: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------- Browser Session Persistence ---------------
    # Path inside storage/browser_sessions/ holding saved Playwright cookies
    browser_storage_path: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True
    )
    has_valid_browser_session: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    last_browser_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------- Anti-Ban Throttling & Daily Quotas ---------------
    daily_post_limit: Mapped[int] = mapped_column(
        Integer, 
        default=10, 
        nullable=False
    )
    daily_posts_sent: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )

    daily_dm_limit: Mapped[int] = mapped_column(
        Integer, 
        default=15, 
        nullable=False
    )
    daily_dms_sent: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )

    # Tracks when the 24-hour quota counter was last reset
    daily_counters_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    # Cooldown enforcement
    last_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------- Metadata & Diagnostics ---------------
    follower_count: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    profile_image_url: Mapped[str | None] = mapped_column(
        String(500), 
        nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # --------------- Operational Helper Methods ---------------
    def can_post_today(self) -> bool:
        """Checks if the account is within its safe daily posting limits."""
        self._check_and_reset_daily_quotas()
        if not self.is_active or self.status != AccountStatus.ACTIVE:
            return False
        if self.is_in_cooldown():
            return False
        return self.daily_posts_sent < self.daily_post_limit

    def can_send_dm_today(self) -> bool:
        """Checks if the account is within its safe outbound cold DM limits."""
        self._check_and_reset_daily_quotas()
        if not self.is_active or self.status != AccountStatus.ACTIVE:
            return False
        if self.is_in_cooldown():
            return False
        return self.daily_dms_sent < self.daily_dm_limit

    def is_in_cooldown(self) -> bool:
        """Checks if the account is currently in a rate-limit cooldown window."""
        if not self.cooldown_until:
            return False
        cooldown = (
            self.cooldown_until.replace(tzinfo=UTC)
            if self.cooldown_until.tzinfo is None
            else self.cooldown_until
        )
        return datetime.now(UTC) < cooldown

    def _check_and_reset_daily_quotas(self) -> None:
        """Resets counters if 24 hours have elapsed since the last reset."""
        now = datetime.now(UTC)
        if not self.daily_counters_reset_at:
            self.daily_counters_reset_at = now
            return

        reset_at = (
            self.daily_counters_reset_at.replace(tzinfo=UTC)
            if self.daily_counters_reset_at.tzinfo is None
            else self.daily_counters_reset_at
        )

        if (now - reset_at).total_seconds() >= 86400:
            self.daily_posts_sent = 0
            self.daily_dms_sent = 0
            self.daily_counters_reset_at = now
