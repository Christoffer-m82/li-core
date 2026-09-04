"""Transport-neutral profile use cases behind an independently verified identity.

This module does not verify tokens, parse multipart requests or choose storage paths.
An HTTP adapter must cryptographically verify the workload identity before constructing
VerifiedWorkloadIdentity, and the injected ProfileState repository must already be bound
to the one server-configured owner profile.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass

from decoder_process import DecoderProcess
from profile_state import ABSENT, ProfileConflict, ProfileState, valid_revision
from upload_input import collect_upload


class ProfileAccessDenied(PermissionError):
    """The verified caller is not the configured BFF workload."""


@dataclass(frozen=True)
class VerifiedWorkloadIdentity:
    """Claims produced by a future cryptographic transport verifier, never browser input."""

    audience: str
    subject: str


class ProfileApplication:
    def __init__(
        self,
        state: ProfileState,
        decoder: DecoderProcess,
        *,
        expected_audience: str,
        allowed_subject: str,
    ) -> None:
        if not isinstance(state, ProfileState) or not hasattr(decoder, "normalize"):
            raise TypeError("Profile application dependencies are invalid.")
        for value in (expected_audience, allowed_subject):
            if not isinstance(value, str) or not 1 <= len(value) <= 512 or not value.isascii():
                raise ValueError("Profile identity configuration is invalid.")
        self._state = state
        self._decoder = decoder
        self._expected_audience = expected_audience
        self._allowed_subject = allowed_subject

    def _authorize(self, caller: VerifiedWorkloadIdentity) -> None:
        if (
            not isinstance(caller, VerifiedWorkloadIdentity)
            or caller.audience != self._expected_audience
            or caller.subject != self._allowed_subject
        ):
            raise ProfileAccessDenied("Profile access denied.")

    def _preflight_revision(self, expected: str) -> None:
        if expected != ABSENT and not valid_revision(expected):
            raise ProfileConflict("Refresh your profile before saving changes.")
        current = self._state.metadata()["revision"]
        if current != expected:
            raise ProfileConflict("Your profile changed. Refresh before saving.")

    def metadata(self, caller: VerifiedWorkloadIdentity) -> dict[str, str]:
        self._authorize(caller)
        return self._state.metadata()

    def image(self, caller: VerifiedWorkloadIdentity) -> bytes | None:
        self._authorize(caller)
        return self._state.image()

    async def replace(
        self,
        caller: VerifiedWorkloadIdentity,
        chunks: AsyncIterable[bytes],
        *,
        media_type: str,
        declared_file_length: str | None,
        expected_revision: str,
    ) -> dict[str, str]:
        self._authorize(caller)
        self._preflight_revision(expected_revision)
        upload = await collect_upload(chunks, media_type, declared_file_length)
        normalized = await self._decoder.normalize(upload)
        return self._state.replace(normalized, expected_revision)

    def remove(self, caller: VerifiedWorkloadIdentity, *, expected_revision: str) -> dict[str, str]:
        self._authorize(caller)
        return self._state.remove(expected_revision)
