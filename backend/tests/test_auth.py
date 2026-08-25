import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import (
    require_api_token,
    require_owner_api_token,
    require_theo_api_token,
)
from app.config import get_settings


LI_TEST_TOKEN = "li-test-token"
THEO_TEST_TOKEN = "theo-test-token"
OWNER_TEST_TOKEN = "owner-test-token"


@pytest.fixture(autouse=True)
def isolated_test_settings(monkeypatch: pytest.MonkeyPatch):
    """
    Use synthetic credentials for authentication tests.

    No real Li OS secrets or database credentials are used.
    """

    test_environment = {
        "LI_OS_API_TOKEN": LI_TEST_TOKEN,
        "LI_OS_THEO_API_TOKEN": THEO_TEST_TOKEN,
        "LI_OS_OWNER_API_TOKEN": OWNER_TEST_TOKEN,
        "LI_OS_DB_HOST": "test.invalid",
        "LI_OS_DB_PORT": "5432",
        "LI_OS_DB_NAME": "postgres",
        "LI_OS_DB_USER": "li_backend_runtime.test",
        "LI_OS_DB_PASSWORD": "synthetic-password",
        "LI_OS_DB_SSLMODE": "require",
        "LI_OS_THEO_DB_USER": "li_theo_runtime.test",
        "LI_OS_THEO_DB_PASSWORD": "synthetic-theo-password",
        "LI_OS_OWNER_DB_USER": "li_owner_runtime.test",
        "LI_OS_OWNER_DB_PASSWORD": "synthetic-owner-password",
    }

    for name, value in test_environment.items():
        monkeypatch.setenv(name, value)

    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def assert_unauthorized(
    auth_function,
    token: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        auth_function(
            credentials=bearer(token),
        )

    assert exc_info.value.status_code == 401


def test_li_token_authority_boundary() -> None:
    require_api_token(
        credentials=bearer(LI_TEST_TOKEN),
    )

    assert_unauthorized(
        require_theo_api_token,
        LI_TEST_TOKEN,
    )

    assert_unauthorized(
        require_owner_api_token,
        LI_TEST_TOKEN,
    )


def test_theo_token_authority_boundary() -> None:
    require_theo_api_token(
        credentials=bearer(THEO_TEST_TOKEN),
    )

    assert_unauthorized(
        require_api_token,
        THEO_TEST_TOKEN,
    )

    assert_unauthorized(
        require_owner_api_token,
        THEO_TEST_TOKEN,
    )


def test_owner_token_authority_boundary() -> None:
    require_owner_api_token(
        credentials=bearer(OWNER_TEST_TOKEN),
    )

    assert_unauthorized(
        require_api_token,
        OWNER_TEST_TOKEN,
    )

    assert_unauthorized(
        require_theo_api_token,
        OWNER_TEST_TOKEN,
    )


def test_missing_credentials_are_rejected() -> None:
    for auth_function in (
        require_api_token,
        require_theo_api_token,
        require_owner_api_token,
    ):
        with pytest.raises(HTTPException) as exc_info:
            auth_function(
                credentials=None,
            )

        assert exc_info.value.status_code == 401