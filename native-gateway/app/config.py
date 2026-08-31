from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LI_NATIVE_", extra="ignore")

    environment: str = "development"
    backend_url: str = "http://localhost:8000"
    backend_audience: str = "http://localhost:8000"
    backend_api_token: SecretStr = SecretStr("development-token")
    token_signing_key: SecretStr = SecretStr("development-signing-key-change-me")
    google_client_ids: list[str] = Field(default_factory=list)
    allowed_email: str = "Christoffer.Mellden@gmail.com"
    access_token_seconds: int = Field(default=600, ge=60, le=900)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    request_timeout_seconds: float = Field(default=30, ge=1, le=60)

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        if self.environment.lower() == "production":
            signing_key = self.token_signing_key.get_secret_value()
            backend_token = self.backend_api_token.get_secret_value()
            if len(signing_key) < 32 or signing_key.startswith("development-"):
                raise ValueError("Production signing key must be at least 32 characters.")
            if len(backend_token) < 32 or backend_token.startswith("development-"):
                raise ValueError("Production backend token must be supplied by Secret Manager.")
            if not self.google_client_ids:
                raise ValueError("At least one native Google client ID is required.")
            if not self.backend_url.startswith("https://"):
                raise ValueError("Production backend URL must use HTTPS.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
