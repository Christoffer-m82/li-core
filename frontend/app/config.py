from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LI_WEB_", extra="ignore")

    environment: str = "development"
    public_origin: str = "http://localhost:8080"
    backend_url: str = "https://li-os-7gyegrz7vq-ew.a.run.app"
    backend_audience: str = "https://li-os-7gyegrz7vq-ew.a.run.app"
    profile_service_url: str = ""
    profile_service_audience: str = ""
    li_api_token: SecretStr = SecretStr("development-token")
    owner_api_token: SecretStr = SecretStr("development-owner-token")
    session_secret: SecretStr = SecretStr("development-session-secret-change-me")
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    allowed_email: str = "Christoffer.Mellden@gmail.com"
    request_timeout_seconds: float = Field(default=60, ge=1, le=180)
    profile_request_timeout_seconds: float = Field(default=30, ge=1, le=60)

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
