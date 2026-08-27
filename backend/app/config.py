from functools import lru_cache

from pydantic import SecretStr
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
    log_level: str = "INFO"

    # Application authentication
    api_token: SecretStr
    theo_api_token: SecretStr
    owner_api_token: SecretStr

    # Claude / Anthropic
    anthropic_api_key: SecretStr
    claude_model: str = "claude-opus-5"
    claude_max_tokens: int = 2048

    # Optional Li-owned live research provider
    brave_search_api_key: SecretStr | None = None
    brave_search_timeout_seconds: float = 10.0

    # Optional Li-owned Google Calendar OAuth provider. Secrets belong in the
    # deployment secret manager; the backend never exposes them to specialists.
    google_calendar_client_id: SecretStr | None = None
    google_calendar_client_secret: SecretStr | None = None
    google_calendar_refresh_token: SecretStr | None = None
    google_calendar_id: str = "primary"
    google_calendar_timeout_seconds: float = 10.0

    # Shared database settings
    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: SecretStr
    db_sslmode: str = "require"

    # Theo database runtime
    theo_db_user: str
    theo_db_password: SecretStr

    # Owner database runtime
    owner_db_user: str
    owner_db_password: SecretStr

    model_config = SettingsConfigDict(
        env_prefix="LI_OS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def database_connect_kwargs(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password.get_secret_value(),
            "sslmode": self.db_sslmode,
        }

    def theo_database_connect_kwargs(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.theo_db_user,
            "password": self.theo_db_password.get_secret_value(),
            "sslmode": self.db_sslmode,
        }

    def owner_database_connect_kwargs(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.owner_db_user,
            "password": self.owner_db_password.get_secret_value(),
            "sslmode": self.db_sslmode,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
