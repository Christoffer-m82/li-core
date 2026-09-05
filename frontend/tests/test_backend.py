import asyncio

import pytest
from google.auth.exceptions import DefaultCredentialsError

from app.backend import BackendUnavailable, request_backend
from app.config import Settings


def test_missing_workload_identity_is_reported_as_backend_unavailable(monkeypatch):
    def missing_identity(_audience, _minute):
        raise DefaultCredentialsError("synthetic credential detail must not escape")

    monkeypatch.setattr("app.backend._identity_token", missing_identity)

    with pytest.raises(BackendUnavailable, match="Backend workload identity is unavailable"):
        asyncio.run(request_backend(Settings(), "GET", "/ready"))
