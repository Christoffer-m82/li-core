"""Atomic single-object profile repository over a generation-conditioned store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from profile_state import ABSENT, MAX_PHOTO_BYTES, RepositoryError, Snapshot

MAGIC = b"LI_PROFILE_V1\0"
REVISION_BYTES = 36
PHOTO = b"P"
EMPTY = b"E"
MAX_OBJECT_BYTES = len(MAGIC) + REVISION_BYTES + 1 + MAX_PHOTO_BYTES


class ObjectStoreError(Exception):
    """Provider adapters use this for unavailable or uncertain object operations."""


@dataclass(frozen=True)
class VersionedObject:
    generation: int
    contents: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("Invalid object generation.")
        if not isinstance(self.contents, bytes) or not 1 <= len(self.contents) <= MAX_OBJECT_BYTES:
            raise ValueError("Invalid stored object.")


class ConditionalObjectStore(Protocol):
    """Already bound to one private object; paths never enter repository calls."""

    def read(self) -> VersionedObject | None: ...

    def write(self, contents: bytes, *, if_generation: int) -> bool:
        """Use generation 0 for create-if-absent; False means the condition lost a race."""
        ...


def _encode(snapshot: Snapshot) -> bytes:
    marker = PHOTO if snapshot.photo is not None else EMPTY
    return MAGIC + snapshot.revision.encode("ascii") + marker + (snapshot.photo or b"")


def _decode(contents: bytes) -> Snapshot:
    if not isinstance(contents, bytes) or not len(MAGIC) + REVISION_BYTES + 1 <= len(contents) <= MAX_OBJECT_BYTES:
        raise RepositoryError("Profile storage is unavailable.")
    if not contents.startswith(MAGIC):
        raise RepositoryError("Profile storage is unavailable.")
    offset = len(MAGIC)
    try:
        revision = contents[offset:offset + REVISION_BYTES].decode("ascii")
        marker = contents[offset + REVISION_BYTES:offset + REVISION_BYTES + 1]
        payload = contents[offset + REVISION_BYTES + 1:]
        if marker == EMPTY and payload:
            raise ValueError
        if marker not in (PHOTO, EMPTY):
            raise ValueError
        return Snapshot(revision, payload if marker == PHOTO else None)
    except (UnicodeDecodeError, ValueError):
        raise RepositoryError("Profile storage is unavailable.") from None


class ObjectRepository:
    """Maps hidden provider generations to the ProfileState compare-and-swap contract."""

    def __init__(self, store: ConditionalObjectStore) -> None:
        if not hasattr(store, "read") or not hasattr(store, "write"):
            raise TypeError("Profile object store is invalid.")
        self._store = store

    def _read_object(self) -> VersionedObject | None:
        try:
            stored = self._store.read()
        except ObjectStoreError:
            raise RepositoryError("Profile storage is unavailable.") from None
        if stored is not None and not isinstance(stored, VersionedObject):
            raise RepositoryError("Profile storage is unavailable.")
        return stored

    def read(self) -> Snapshot | None:
        stored = self._read_object()
        return _decode(stored.contents) if stored else None

    def compare_and_swap(self, expected: str, replacement: Snapshot) -> bool:
        if not isinstance(replacement, Snapshot):
            raise RepositoryError("Profile storage is unavailable.")
        stored = self._read_object()
        current = _decode(stored.contents) if stored else None
        actual = current.revision if current else ABSENT
        if actual != expected:
            return False
        try:
            result = self._store.write(
                _encode(replacement), if_generation=stored.generation if stored else 0,
            )
        except ObjectStoreError:
            raise RepositoryError("Profile storage is unavailable.") from None
        if type(result) is not bool:
            raise RepositoryError("Profile storage is unavailable.")
        return result
