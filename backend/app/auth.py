from hmac import compare_digest

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings


li_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Li OS API Token",
    description="Private bearer token for normal Li OS endpoints.",
)


theo_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Theo API Token",
    description="Separate privileged bearer token for Theo review endpoints.",
)


owner_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Owner API Token",
    description="Separate bearer token for explicit owner-confirmation endpoints.",
)

native_gateway_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Native Gateway API Token",
    description="Scoped server-side token for the authenticated native gateway.",
)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(
        li_bearer_scheme
    ),
) -> None:
    """
    Require the normal Li OS bearer token.
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    expected_token = settings.api_token.get_secret_value()

    if not compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_theo_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(
        theo_bearer_scheme
    ),
) -> None:
    """
    Require Theo's separate privileged bearer token.
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Theo authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    expected_token = settings.theo_api_token.get_secret_value()

    if not compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Theo authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_owner_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(
        owner_bearer_scheme
    ),
) -> None:
    """
    Require the owner's separate explicit-confirmation bearer token.
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Owner authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    expected_token = settings.owner_api_token.get_secret_value()

    if not compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid owner authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_native_gateway_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(native_gateway_bearer_scheme),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Native gateway authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expected = get_settings().native_gateway_api_token.get_secret_value()
    if not compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid native gateway credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
