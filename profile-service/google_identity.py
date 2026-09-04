"""Google-signed workload ID-token verifier for the private profile boundary.

The production constructor loads google-auth lazily. Tests inject a cryptographic verifier and
make no certificate, metadata-server, identity or provider request.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from http_contract import IdentityVerificationError
from profile_application import VerifiedWorkloadIdentity

GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
MAX_TOKEN_BYTES = 8192
MAX_CLAIM_BYTES = 512

VerifyToken = Callable[..., Mapping[str, Any]]


class GoogleWorkloadIdentityVerifier:
    """Verify signature/time/audience through google-auth, then minimize trusted claims."""

    def __init__(
        self,
        request: object,
        verify_oauth2_token: VerifyToken,
        verification_errors: tuple[type[Exception], ...],
    ) -> None:
        if request is None or not callable(verify_oauth2_token):
            raise TypeError("Google identity verifier dependency is invalid.")
        if (
            not isinstance(verification_errors, tuple)
            or not verification_errors
            or not all(isinstance(item, type) and issubclass(item, Exception)
                       for item in verification_errors)
            or Exception in verification_errors
        ):
            raise TypeError("Google identity error configuration is invalid.")
        self._request = request
        self._verify_token = verify_oauth2_token
        self._errors = verification_errors

    @classmethod
    def from_google_auth(cls) -> GoogleWorkloadIdentityVerifier:
        """Construct the real verifier only when the separately pinned SDK is installed."""
        try:
            from google.auth import exceptions
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import verify_oauth2_token
        except ImportError:
            raise RuntimeError("Google identity verification is unavailable.") from None
        return cls(Request(), verify_oauth2_token, (ValueError, exceptions.GoogleAuthError))

    def verify(self, token: str, *, audience: str) -> VerifiedWorkloadIdentity:
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= MAX_TOKEN_BYTES
            or not token.isascii()
            or any(character.isspace() for character in token)
            or not isinstance(audience, str)
            or not 1 <= len(audience) <= MAX_CLAIM_BYTES
            or not audience.isascii()
            or any(ord(character) < 33 or ord(character) == 127 for character in audience)
        ):
            raise IdentityVerificationError("Authentication failed.")
        try:
            claims = self._verify_token(token, self._request, audience=audience)
        except self._errors:
            raise IdentityVerificationError("Authentication failed.") from None
        if not isinstance(claims, Mapping):
            raise IdentityVerificationError("Authentication failed.")
        issuer = claims.get("iss")
        subject = claims.get("sub")
        if (
            not isinstance(issuer, str)
            or issuer not in GOOGLE_ISSUERS
            or claims.get("aud") != audience
            or not isinstance(subject, str)
            or not 1 <= len(subject) <= MAX_CLAIM_BYTES
            or not subject.isascii()
            or any(ord(character) < 33 or ord(character) == 127 for character in subject)
        ):
            raise IdentityVerificationError("Authentication failed.")
        return VerifiedWorkloadIdentity(audience=audience, subject=subject)
