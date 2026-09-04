import asyncio

import httpx
import pytest

from app.config import Settings
from app.profile_service import (
    MAX_PROFILE_SERVICE_RESPONSE_BYTES,
    ProfileServiceUnavailable,
    profile_service_configured,
    request_profile_service,
)


class StreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_args):
        return False


class Client:
    response = None
    calls = []

    def __init__(self, **kwargs):
        self.calls.append(("configuration", kwargs))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return StreamContext(self.response)


def configured(**values):
    configuration = {
        "profile_service_url": "https://profile.example",
        "profile_service_audience": "https://profile.example",
    }
    configuration.update(values)
    return Settings(**configuration)


def test_configuration_requires_both_values_and_safe_production_url(monkeypatch):
    assert profile_service_configured(Settings()) is False
    assert profile_service_configured(Settings(profile_service_url="https://profile.example")) is False
    calls = 0

    def token(_audience):
        nonlocal calls
        calls += 1
        return "synthetic.identity.token"

    monkeypatch.setattr("app.profile_service.cloud_run_identity_token", token)
    for settings in (
        Settings(profile_service_url="https://profile.example", profile_service_audience=""),
        configured(environment="production", profile_service_url="http://profile.example"),
        configured(profile_service_url="https://user:pass@profile.example"),
        configured(profile_service_url="https://profile.example/path"),
        configured(profile_service_url="https://profile .example"),
        configured(profile_service_url="https://[invalid"),
    ):
        with pytest.raises(ProfileServiceUnavailable):
            asyncio.run(request_profile_service(settings, "GET", "/v1/profile"))
    assert calls == 0


def test_metadata_request_uses_only_workload_identity_and_bounded_response(monkeypatch):
    Client.calls = []
    Client.response = httpx.Response(
        200,
        headers={"content-type": "application/json; charset=utf-8"},
        json={"state": "empty", "revision": "absent"},
    )
    monkeypatch.setattr("app.profile_service.cloud_run_identity_token", lambda audience: "synthetic.identity.token")
    monkeypatch.setattr("app.profile_service.httpx.AsyncClient", Client)
    result = asyncio.run(request_profile_service(configured(), "GET", "/v1/profile"))
    assert result.status == 200
    assert result.content_type == "application/json"
    assert b"empty" in result.body
    _, options = Client.calls[0]
    assert options["follow_redirects"] is False
    method, url, request = Client.calls[1]
    assert (method, url) == ("GET", "https://profile.example/v1/profile")
    assert request["headers"] == {"Authorization": "Bearer synthetic.identity.token"}
    assert "X-Serverless-Authorization" not in request["headers"]


def test_replacement_forwards_only_raw_file_contract(monkeypatch):
    Client.calls = []
    Client.response = httpx.Response(
        200, headers={"content-type": "application/json"},
        json={"state": "available", "revision": "00000000-0000-0000-0000-000000000001"},
    )
    monkeypatch.setattr("app.profile_service.cloud_run_identity_token", lambda audience: "synthetic.identity.token")
    monkeypatch.setattr("app.profile_service.httpx.AsyncClient", Client)
    result = asyncio.run(request_profile_service(
        configured(), "PUT", "/v1/profile", revision="absent",
        content_type="image/png", content_length=12, body=b"syntheticpng",
    ))
    assert result.status == 200
    request = Client.calls[1][2]
    assert request["headers"]["If-Match"] == "absent"
    assert request["headers"]["Content-Type"] == "image/png"
    assert request["headers"]["Content-Length"] == "12"
    assert request["content"] == b"syntheticpng"


@pytest.mark.parametrize(
    ("response", "operation"),
    [
        (httpx.Response(302, headers={"content-type": "application/json"}), ("GET", "/v1/profile")),
        (httpx.Response(200, headers={"content-type": "text/html"}, content=b"bad"), ("GET", "/v1/profile")),
        (httpx.Response(200, headers={"content-type": "image/jpeg"},
                        content=b"x" * (MAX_PROFILE_SERVICE_RESPONSE_BYTES + 1)),
         ("GET", "/v1/profile/image")),
    ],
)
def test_unexpected_status_type_and_size_fail_closed(monkeypatch, response, operation):
    Client.calls = []
    Client.response = response
    monkeypatch.setattr("app.profile_service.cloud_run_identity_token", lambda audience: "synthetic.identity.token")
    monkeypatch.setattr("app.profile_service.httpx.AsyncClient", Client)
    with pytest.raises(ProfileServiceUnavailable):
        asyncio.run(request_profile_service(configured(), *operation))


def test_invalid_identity_and_unsupported_operation_fail_before_network(monkeypatch):
    Client.calls = []
    monkeypatch.setattr("app.profile_service.httpx.AsyncClient", Client)
    monkeypatch.setattr("app.profile_service.cloud_run_identity_token", lambda audience: "has whitespace")
    with pytest.raises(ProfileServiceUnavailable):
        asyncio.run(request_profile_service(configured(), "GET", "/v1/profile"))
    with pytest.raises(ValueError):
        asyncio.run(request_profile_service(configured(), "POST", "/v1/profile"))
    with pytest.raises(ValueError):
        asyncio.run(request_profile_service(
            configured(), "PUT", "/v1/profile", revision="absent",
            content_type="image/gif", content_length=1, body=b"x",
        ))
    with pytest.raises(ValueError):
        asyncio.run(request_profile_service(configured(), "DELETE", "/v1/profile", revision="bad value"))
    assert Client.calls == []
