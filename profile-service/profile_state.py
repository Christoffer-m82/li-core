"""Provider-free profile state transitions; not an authenticated upload endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID, uuid4

ABSENT = "absent"
MAX_PHOTO_BYTES = 512 * 1024


class ProfileConflict(Exception):
    """The caller must refresh before attempting another mutation."""


class ProfileUnavailable(Exception):
    """Storage failed; an uncertain mutation must be reconciled by reading."""


class RepositoryError(Exception):
    """Adapters must translate provider failures to this boundary exception."""


class InvalidPhoto(ValueError):
    """Normalized output failed a boundary check (not full image validation)."""


def valid_revision(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def check_normalized(contents: bytes) -> None:
    # Only a trusted decoder may produce this input. Markers do not prove image safety.
    if (
        not isinstance(contents, bytes)
        or not 4 <= len(contents) <= MAX_PHOTO_BYTES
        or not contents.startswith(b"\xff\xd8")
        or not contents.endswith(b"\xff\xd9")
    ):
        raise InvalidPhoto("Normalized profile image is invalid or too large.")


@dataclass(frozen=True)
class Snapshot:
    revision: str
    photo: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not valid_revision(self.revision):
            raise ValueError("Invalid stored profile revision.")
        if self.photo is not None:
            check_normalized(self.photo)

    def metadata(self) -> dict[str, str]:
        return {"state": "available" if self.photo is not None else "empty",
                "revision": self.revision}


class Repository(Protocol):
    """Owner-bound repository; absence is None, errors must raise, never masquerade as absence."""

    def read(self) -> Snapshot | None: ...

    def compare_and_swap(self, expected: str, replacement: Snapshot) -> bool:
        """Atomically compare current revision (or ABSENT) and replace; False on mismatch."""
        ...


class ProfileState:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def _read(self) -> Snapshot | None:
        try:
            snapshot = self._repository.read()
        except RepositoryError:
            raise ProfileUnavailable("Profile storage is unavailable.") from None
        if snapshot is not None and not isinstance(snapshot, Snapshot):
            raise ProfileUnavailable("Profile storage is unavailable.")
        return snapshot

    def metadata(self) -> dict[str, str]:
        snapshot = self._read()
        return snapshot.metadata() if snapshot else {"state": "empty", "revision": ABSENT}

    def image(self) -> bytes | None:
        snapshot = self._read()
        return snapshot.photo if snapshot else None

    def _current(self, expected: str) -> Snapshot | None:
        if expected != ABSENT and not valid_revision(expected):
            raise ProfileConflict("Refresh your profile before saving changes.")
        snapshot = self._read()
        actual = snapshot.revision if snapshot else ABSENT
        if expected != actual:
            raise ProfileConflict("Your profile changed. Refresh before saving.")
        return snapshot

    def _write(self, expected: str, photo: bytes | None) -> dict[str, str]:
        replacement = Snapshot(str(uuid4()), photo)
        try:
            result = self._repository.compare_and_swap(expected, replacement)
        except RepositoryError:
            raise ProfileUnavailable("Profile save could not be confirmed. Refresh to check its state.") from None
        if type(result) is not bool:
            raise ProfileUnavailable("Profile save could not be confirmed. Refresh to check its state.")
        if not result:
            raise ProfileConflict("Your profile changed. Refresh before saving.")
        return replacement.metadata()

    def replace(self, normalized_photo: bytes, expected: str) -> dict[str, str]:
        check_normalized(normalized_photo)
        self._current(expected)
        return self._write(expected, normalized_photo)

    def remove(self, expected: str) -> dict[str, str]:
        snapshot = self._current(expected)
        if snapshot is None:
            return {"state": "empty", "revision": ABSENT}
        if snapshot.photo is None:
            return snapshot.metadata()
        return self._write(expected, None)
