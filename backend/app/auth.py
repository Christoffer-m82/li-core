from hmac import compare_digest

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings


bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Li OS API Token",
    description="Private bearer token required for protected Li OS endpoints.",
)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    """
    Require the private Li OS bearer token.

    Token comparison uses constant-time comparison to avoid leaking
    useful information through timing differences.
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