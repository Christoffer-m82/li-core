from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
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
    allowed_origins: list[str] = Field(default_factory=list)
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    trust_proxy_headers: bool = False

    # Application authentication
    api_token: SecretStr
    theo_api_token: SecretStr
    owner_api_token: SecretStr

    # Claude / Anthropic
    anthropic_api_key: SecretStr
    claude_model: str = "claude-sonnet-5"
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

    # Optional Li-owned Gmail OAuth provider. Read/search requires gmail.readonly;
    # draft creation additionally requires gmail.compose. Sending is not exposed.
    google_gmail_client_id: SecretStr | None = None
    google_gmail_client_secret: SecretStr | None = None
    google_gmail_refresh_token: SecretStr | None = None
    google_gmail_user_id: str = "me"
    google_gmail_timeout_seconds: float = 10.0

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

    # Governed private artifacts. The bucket is private and accessed only by
    # the backend runtime service account.
    artifact_bucket: str = ""
    artifact_default_retention_days: int = Field(default=30, ge=1, le=365)

    model_config = SettingsConfigDict(
        env_prefix="LI_OS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        if any(
            len(secret.get_secret_value()) < 32
            for secret in (self.api_token, self.theo_api_token, self.owner_api_token)
        ):
            raise ValueError("Production API tokens must contain at least 32 characters.")
        if "*" in self.allowed_origins:
            raise ValueError("Wildcard CORS is forbidden in production.")
        if self.db_sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Production database connections must require TLS.")
        self._validate_optional_group(
            "Google Calendar",
            self.google_calendar_client_id,
            self.google_calendar_client_secret,
            self.google_calendar_refresh_token,
        )
        self._validate_optional_group(
            "Google Gmail",
            self.google_gmail_client_id,
            self.google_gmail_client_secret,
            self.google_gmail_refresh_token,
        )
        return self

    @staticmethod
    def _validate_optional_group(name: str, *values: SecretStr | None) -> None:
        configured = [bool(value and value.get_secret_value().strip()) for value in values]
        if any(configured) and not all(configured):
            raise ValueError(f"{name} credentials must be configured as a complete set.")

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
