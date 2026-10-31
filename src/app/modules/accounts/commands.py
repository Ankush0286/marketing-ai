from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.common.enums import AccountStatus, AuthMethod, PlatformType


@dataclass(frozen=True)
class CreateAccountCommand:
    platform: PlatformType
    handle: str
    display_name: str | None = None
    auth_method: AuthMethod = AuthMethod.HYBRID
    daily_post_limit: int = 10
    daily_dm_limit: int = 15
    browser_storage_path: str | None = None

    # Raw API credentials to be encrypted by the service
    access_token: str | None = None
    refresh_token: str | None = None
    token_secret: str | None = None
    api_key: str | None = None
    api_secret: str | None = None


@dataclass(frozen=True)
class UpdateAccountCommand:
    account_id: UUID
    display_name: str | None = None
    status: AccountStatus | None = None
    is_active: bool | None = None
    daily_post_limit: int | None = None
    daily_dm_limit: int | None = None
    extra_metadata: dict[str, Any] | None = None

    # Credential rotation
    access_token: str | None = None
    refresh_token: str | None = None
    api_key: str | None = None
    api_secret: str | None = None


@dataclass(frozen=True)
class UpdateCooldownCommand:
    account_id: UUID
    cooldown_until: datetime
    error_message: str | None = None
