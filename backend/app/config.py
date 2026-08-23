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

    api_token: SecretStr
    theo_api_token: SecretStr

    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: SecretStr
    db_sslmode: str = "require"

    theo_db_user: str
    theo_db_password: SecretStr

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


@lru_cache
def get_settings() -> Settings:
    return Settings()