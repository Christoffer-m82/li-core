import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.production import JsonFormatter, SecurityMiddleware

BASE = {
    "api_token": "a" * 32,
    "theo_api_token": "b" * 32,
    "owner_api_token": "c" * 32,
    "native_gateway_api_token": "n" * 32,
    "anthropic_api_key": "synthetic",
    "db_host": "test.invalid",
    "db_user": "li_backend_runtime.test",
    "db_password": "synthetic",
    "theo_db_user": "li_theo_runtime.test",
    "theo_db_password": "synthetic",
    "owner_db_user": "li_owner_runtime.test",
    "owner_db_password": "synthetic",
}


def test_default_claude_model_is_current_sonnet() -> None:
    settings = Settings(_env_file=None, **BASE)

    assert settings.claude_model == "claude-sonnet-5"


def test_claude_model_can_be_overridden() -> None:
    settings = Settings(claude_model="claude-opus-5", _env_file=None, **BASE)

    assert settings.claude_model == "claude-opus-5"


def test_production_rejects_short_tokens() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(environment="production", _env_file=None, **{**BASE, "api_token": "short"})


def test_production_rejects_partial_oauth_configuration() -> None:
    with pytest.raises(ValidationError, match="complete set"):
        Settings(
            environment="production",
            google_gmail_client_id="only-one",
            _env_file=None,
            **BASE,
        )


def test_rate_limit_and_security_headers() -> None:
    test_app = FastAPI()
    test_app.add_middleware(
        SecurityMiddleware, requests=1, window_seconds=60, trust_proxy_headers=False
    )

    @test_app.get("/")
    def root() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(test_app) as client:
        first = client.get("/")
        second = client.get("/")
    assert first.headers["x-content-type-options"] == "nosniff"
    assert second.status_code == 429


def test_json_formatter_redacts_sensitive_names() -> None:
    import logging

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "api_token leaked", (), None)
    rendered = json.loads(JsonFormatter().format(record))
    assert "api_token" not in rendered["message"]
    assert "[REDACTED]" in rendered["message"]
