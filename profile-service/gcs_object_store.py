"""Google Cloud Storage blob adapter with generation-conditioned operations.

The caller injects one already-bound private Blob plus the installed SDK's exception classes.
This module never accepts a bucket, object path, client, credential or billing project.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from object_repository import (
    MAX_OBJECT_BYTES,
    ObjectStoreError,
    VersionedObject,
)

DEFAULT_TIMEOUT_SECONDS = 10


class BoundBlob(Protocol):
    generation: object

    def reload(self, *, timeout: float, retry: None) -> None: ...

    def download_to_file(
        self,
        file_object,
        *,
        raw_download: bool,
        if_generation_match: int,
        timeout: float,
        checksum: str,
        retry: None,
        single_shot_download: bool,
    ) -> None: ...

    def upload_from_string(
        self,
        data: bytes,
        *,
        content_type: str,
        if_generation_match: int,
        timeout: float,
        checksum: str,
        retry: None,
    ) -> None: ...


class NamespaceVerifier(Protocol):
    def verify(self, *, timeout: float, retry: None) -> bool:
        """Return exactly True only when object-level not-found can safely mean absence."""
        ...


def _exception_tuple(value: object, name: str) -> tuple[type[Exception], ...]:
    if (
        not isinstance(value, tuple)
        or not value
        or not all(isinstance(item, type) and issubclass(item, Exception) for item in value)
    ):
        raise TypeError(f"Invalid {name} exception configuration.")
    return value


@dataclass(frozen=True)
class ProviderExceptions:
    not_found: tuple[type[Exception], ...]
    precondition_failed: tuple[type[Exception], ...]
    unavailable: tuple[type[Exception], ...]

    def __post_init__(self) -> None:
        not_found = _exception_tuple(self.not_found, "not-found")
        precondition = _exception_tuple(self.precondition_failed, "precondition")
        _exception_tuple(self.unavailable, "unavailable")
        if set(not_found) & set(precondition):
            raise TypeError("Provider exception categories overlap.")


class _ObjectTooLarge(Exception):
    pass


class _BoundedBuffer(io.BytesIO):
    def write(self, data) -> int:
        try:
            size = memoryview(data).nbytes
        except TypeError:
            raise _ObjectTooLarge from None
        if self.tell() + size > MAX_OBJECT_BYTES:
            raise _ObjectTooLarge
        return super().write(data)


class GoogleCloudObjectStore:
    """Adapt one already-bound GCS Blob to the conditional object-store contract."""

    def __init__(
        self,
        blob: BoundBlob,
        exceptions: ProviderExceptions,
        namespace_verifier: NamespaceVerifier,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not all(callable(getattr(blob, name, None))
                   for name in ("reload", "download_to_file", "upload_from_string")):
            raise TypeError("Profile storage blob is invalid.")
        if not isinstance(exceptions, ProviderExceptions):
            raise TypeError("Profile storage exceptions are invalid.")
        if not callable(getattr(namespace_verifier, "verify", None)):
            raise TypeError("Profile storage namespace verifier is invalid.")
        if type(timeout_seconds) not in {int, float} or not 1 <= timeout_seconds <= 60:
            raise ValueError("Profile storage timeout is invalid.")
        self._blob = blob
        self._exceptions = exceptions
        self._namespace_verifier = namespace_verifier
        self._timeout = float(timeout_seconds)

    def read(self) -> VersionedObject | None:
        try:
            self._blob.reload(timeout=self._timeout, retry=None)
        except self._exceptions.not_found:
            try:
                verified = self._namespace_verifier.verify(timeout=self._timeout, retry=None)
            except (
                *self._exceptions.not_found,
                *self._exceptions.precondition_failed,
                *self._exceptions.unavailable,
            ):
                raise ObjectStoreError("Profile object storage is unavailable.") from None
            if verified is not True:
                raise ObjectStoreError("Profile object storage is unavailable.")
            return None
        except self._exceptions.unavailable:
            raise ObjectStoreError("Profile object storage is unavailable.") from None

        generation = self._blob.generation
        if type(generation) is not int or generation < 1:
            raise ObjectStoreError("Profile object storage is unavailable.")

        output = _BoundedBuffer()
        try:
            self._blob.download_to_file(
                output,
                raw_download=True,
                if_generation_match=generation,
                timeout=self._timeout,
                checksum="auto",
                retry=None,
                single_shot_download=False,
            )
            contents = output.getvalue()
        except (_ObjectTooLarge, *self._exceptions.not_found, *self._exceptions.precondition_failed):
            raise ObjectStoreError("Profile object storage changed during read.") from None
        except self._exceptions.unavailable:
            raise ObjectStoreError("Profile object storage is unavailable.") from None
        finally:
            output.close()

        try:
            return VersionedObject(generation, contents)
        except ValueError:
            raise ObjectStoreError("Profile object storage is unavailable.") from None

    def write(self, contents: bytes, *, if_generation: int) -> bool:
        if (
            not isinstance(contents, bytes)
            or not 1 <= len(contents) <= MAX_OBJECT_BYTES
            or type(if_generation) is not int
            or if_generation < 0
        ):
            raise ObjectStoreError("Profile object write is invalid.")
        try:
            self._blob.upload_from_string(
                contents,
                content_type="application/octet-stream",
                if_generation_match=if_generation,
                timeout=self._timeout,
                checksum="auto",
                retry=None,
            )
            return True
        except self._exceptions.precondition_failed:
            return False
        except self._exceptions.unavailable:
            raise ObjectStoreError("Profile object storage is unavailable.") from None
