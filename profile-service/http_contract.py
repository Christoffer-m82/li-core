"""Private HTTP contract composition; not a web server or token implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from decoder_process import DecoderUnavailable
from profile_application import (
    ProfileAccessDenied,
    ProfileApplication,
    VerifiedWorkloadIdentity,
)
from profile_state import InvalidPhoto, ProfileConflict, ProfileUnavailable
from upload_input import InvalidUpload, UnsupportedUpload, UploadTooLarge

MAX_AUTHORIZATION_BYTES = 8192
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


class IdentityVerificationError(Exception):
    """The token could not be cryptographically verified for the intended audience."""


class WorkloadIdentityVerifier(Protocol):
    def verify(self, token: str, *, audience: str) -> VerifiedWorkloadIdentity: ...


@dataclass(frozen=True)
class PrivateResponse:
    status: int
    body: bytes = field(default=b"", repr=False)
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.status) is not int or not 100 <= self.status <= 599:
            raise ValueError("Invalid private response status.")
        if not isinstance(self.body, bytes):
            raise TypeError("Invalid private response body.")
        if not all(isinstance(key, str) and isinstance(value, str)
                   for key, value in self.headers.items()):
            raise TypeError("Invalid private response headers.")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


def _json(status: int, value: dict[str, str]) -> PrivateResponse:
    body = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return PrivateResponse(status, body, {**PRIVATE_HEADERS, "Content-Type": "application/json"})


def _error(status: int, detail: str) -> PrivateResponse:
    return _json(status, {"detail": detail})


class ProfileHttpContract:
    """Maps verified private-service operations to bounded, generic HTTP responses."""

    def __init__(
        self,
        application: ProfileApplication,
        verifier: WorkloadIdentityVerifier,
        *,
        audience: str,
    ) -> None:
        if not isinstance(application, ProfileApplication) or not hasattr(verifier, "verify"):
            raise TypeError("Profile HTTP dependencies are invalid.")
        if not isinstance(audience, str) or not 1 <= len(audience) <= 512 or not audience.isascii():
            raise ValueError("Profile audience configuration is invalid.")
        self._application = application
        self._verifier = verifier
        self._audience = audience

    def _identity(self, authorization: str | None) -> VerifiedWorkloadIdentity:
        if (
            not isinstance(authorization, str)
            or not authorization.startswith("Bearer ")
            or not 1 <= len(authorization[7:]) <= MAX_AUTHORIZATION_BYTES
            or not authorization[7:].isascii()
            or any(character.isspace() for character in authorization[7:])
        ):
            raise IdentityVerificationError("Authentication required.")
        identity = self._verifier.verify(authorization[7:], audience=self._audience)
        if not isinstance(identity, VerifiedWorkloadIdentity):
            raise IdentityVerificationError("Authentication failed.")
        return identity

    @staticmethod
    def _revision(if_match: str | None) -> str:
        if not isinstance(if_match, str) or not if_match:
            raise ProfileConflict("Refresh your profile before saving changes.")
        return if_match

    def _call(self, authorization: str | None, operation) -> PrivateResponse:
        try:
            return operation(self._identity(authorization))
        except IdentityVerificationError:
            return _error(401, "Authentication required.")
        except ProfileAccessDenied:
            return _error(403, "Profile access denied.")
        except ProfileConflict:
            return _error(409, "Refresh your profile before saving changes.")
        except ProfileUnavailable:
            return _error(503, "Private profile storage is unavailable.")

    def metadata(self, authorization: str | None) -> PrivateResponse:
        return self._call(authorization, lambda identity: _json(
            200, self._application.metadata(identity),
        ))

    def image(self, authorization: str | None) -> PrivateResponse:
        def operation(identity: VerifiedWorkloadIdentity) -> PrivateResponse:
            image = self._application.image(identity)
            if image is None:
                return _error(404, "Profile photo is not set.")
            return PrivateResponse(200, image, {**PRIVATE_HEADERS, "Content-Type": "image/jpeg"})
        return self._call(authorization, operation)

    async def replace(
        self,
        authorization: str | None,
        chunks: AsyncIterable[bytes],
        *,
        content_type: str,
        file_length: str | None,
        if_match: str | None,
    ) -> PrivateResponse:
        try:
            identity = self._identity(authorization)
            revision = self._revision(if_match)
            metadata = await self._application.replace(
                identity, chunks, media_type=content_type,
                declared_file_length=file_length, expected_revision=revision,
            )
            return _json(200, metadata)
        except IdentityVerificationError:
            return _error(401, "Authentication required.")
        except ProfileAccessDenied:
            return _error(403, "Profile access denied.")
        except ProfileConflict:
            return _error(409, "Refresh your profile before saving changes.")
        except UploadTooLarge:
            return _error(413, "Profile photo exceeds the upload limit.")
        except UnsupportedUpload:
            return _error(415, "Use JPEG, PNG or WebP.")
        except (InvalidUpload, InvalidPhoto):
            return _error(422, "Profile photo could not be processed.")
        except (DecoderUnavailable, ProfileUnavailable):
            return _error(503, "Profile photo processing is unavailable.")

    def remove(
        self, authorization: str | None, *, if_match: str | None,
    ) -> PrivateResponse:
        def operation(identity: VerifiedWorkloadIdentity) -> PrivateResponse:
            return _json(200, self._application.remove(
                identity, expected_revision=self._revision(if_match),
            ))
        return self._call(authorization, operation)
