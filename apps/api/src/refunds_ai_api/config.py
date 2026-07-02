from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend environment configuration."""

    model_config = SettingsConfigDict(
        env_file=("../../.env", "../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_db_url: str | None = Field(default=None, alias="SUPABASE_DB_URL")
    database_connect_timeout_seconds: int = Field(
        default=5,
        alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached backend settings loaded from the environment."""
    return Settings()
