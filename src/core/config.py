import os
from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings configured via environment variables."""

    API_VERSION: str
    PROJECT_NAME: str
    ENVIRONMENT: Literal["development", "staging", "production"]

    OPENROUTER_API_KEY: SecretStr

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()