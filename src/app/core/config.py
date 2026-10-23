import os
from pathlib import Path
from typing import Literal
from functools import lru_cache
from pydantic import SecretStr, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    """Application settings configured via environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # App Environment
    API_VERSION: str
    APP_NAME: str
    ENVIRONMENT: Literal["development", "staging", "production"]

    # Turso / libSQL Configuration
    TURSO_DATABASE_URL: str 
    TURSO_AUTH_TOKEN: str 
    LOCAL_DB_PATH: str

    # Database Pool & Engine Settings (for SQLAlchemy)
    DB_ECHO: bool
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int

    OPENROUTER_API_KEY: SecretStr
    SECRET_KEY: SecretStr

    
    @computed_field
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance so the .env file is read and parsed
    only once during application startup.
    """
    return Settings()

settings = get_settings()