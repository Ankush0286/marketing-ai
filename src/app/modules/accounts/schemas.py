from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import AccountStatus, AuthMethod, PlatformType
from app.modules.accounts.commands import CreateAccountCommand, UpdateAccountCommand

# ----------------- Request Schemas (HTTP Ingress) -----------------

class AccountCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/accounts/"""
    platform: PlatformType = Field(..., description="Target platform (twitter, instagram, etc.)")
    handle: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.]+$",
        description="Account username/handle without @ symbol",
        examples=["growth_hacker_ai"]
    )
    display_name: str | None = Field(
        None, 
        max_length=150, 
        examples=["Growth AI"]
    )
    auth_method: AuthMethod = Field(
        default=AuthMethod.HYBRID,
        description="Whether this account uses API keys, browser sessions, or both"
    )
    daily_post_limit: int = Field(
        default=10, 
        ge=1, 
        le=50, 
        description="Max automated posts per 24 hours"
    )
    daily_dm_limit: int = Field(
        default=15, 
        ge=0, 
        le=50, 
        description="Max outbound cold DMs per 24 hours"
    )

    # Plaintext API credentials provided by the user in the UI (encrypted by service)
    access_token: str | None = Field(
        None, 
        description="OAuth user access token"
    )
    refresh_token: str | None = Field(
        None, 
        description="OAuth refresh token"
    )
    token_secret: str | None = Field(
        None, 
        description="OAuth 1.0a token secret"
    )
    api_key: str | None = Field(
        None, description="App / Consumer API key"
    )
    api_secret: str | None = Field(
        None, 
        description="App / Consumer API secret"
    )
    browser_storage_path: str | None = Field(
        None, 
        description="Path to saved Playwright cookies"
    )

    def to_command(self) -> CreateAccountCommand:
        """Converts the HTTP schema into a clean domain command."""
        return CreateAccountCommand(**self.model_dump())


class AccountUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/accounts/{account_id}"""
    display_name: str | None = Field(
        None, 
        max_length=150
    )
    status: AccountStatus | None = None
    is_active: bool | None = None
    daily_post_limit: int | None = Field(
        None, 
        ge=1, 
        le=50
    )
    daily_dm_limit: int | None = Field(
        None, 
        ge=0, 
        le=50
    )
    extra_metadata: dict[str, Any] | None = None

    # Optional credential rotation
    access_token: str | None = None
    refresh_token: str | None = None
    api_key: str | None = None
    api_secret: str | None = None

    def to_command(self, account_id: UUID) -> UpdateAccountCommand:
        """Converts the HTTP patch into a clean domain command."""
        return UpdateAccountCommand(
            account_id=account_id,
            **self.model_dump(exclude_unset=True)
        )


# ----------------- Response Schemas (HTTP Egress) -----------------

class AccountResponse(BaseModel):
    """
    Sanitized public view of a connected account.
    Notice: All encrypted_* columns are completely excluded from serialization.
    """
    id: UUID
    platform: PlatformType
    handle: str
    display_name: str | None = None
    platform_user_id: str | None = None
    status: AccountStatus
    auth_method: AuthMethod
    is_active: bool

    # Quotas & throttling status
    daily_post_limit: int
    daily_posts_sent: int
    daily_dm_limit: int
    daily_dms_sent: int
    cooldown_until: datetime | None = None

    # Browser automation state
    has_valid_browser_session: bool
    last_browser_login_at: datetime | None = None

    # Diagnostics
    follower_count: int | None = None
    profile_image_url: str | None = None
    last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    # Enables reading directly from SQLAlchemy model instances
    model_config = ConfigDict(from_attributes=True)
