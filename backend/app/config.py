from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime configuration for Li OS.

    Sensitive values must come from environment variables or a
    secrets-management system. They must never be committed to GitHub.
    """

    app_name: str = "Li OS Backend"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = Field(
        ...,
        description="Restricted PostgreSQL connection string for Li OS runtime access.",
    )

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="LI_OS_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
