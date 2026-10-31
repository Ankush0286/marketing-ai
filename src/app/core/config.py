from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings configured via environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App Environment
    API_VERSION: str = "v1"
    APP_NAME: str = "Marketing AI Agent"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # Turso / libSQL Configuration
    TURSO_DATABASE_URL: str = ""
    TURSO_AUTH_TOKEN: str = ""
    LOCAL_DB_PATH: str = "storage/local.db"

    # Database Pool & Engine Settings (for SQLAlchemy)
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    SECRET_KEY: SecretStr = SecretStr("default-dev-secret-key-32-bytes!")

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance so the .env file is read and parsed
    only once during application startup.
    """
    return Settings()


settings = get_settings()
