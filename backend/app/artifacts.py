"""Governed private artifact storage for Li OS."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from google.cloud import storage

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")


class ArtifactStorageError(RuntimeError):
    """Raised when private artifact storage cannot complete an operation."""


def safe_filename(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = SAFE_FILENAME.sub("_", name).strip(" .")
    return name[:180] or "artifact"


@dataclass(frozen=True)
class StoredObject:
    object_name: str
    size_bytes: int
    generation: int | None


class PrivateArtifactStore:
    def __init__(self, bucket_name: str) -> None:
        if not bucket_name:
            raise ArtifactStorageError("Artifact bucket is not configured.")
        self.bucket = storage.Client().bucket(bucket_name)

    @staticmethod
    def object_name(owner_id: str, artifact_id: str, filename: str) -> str:
        return f"owners/{owner_id}/artifacts/{artifact_id}/{safe_filename(filename)}"

    def put(
        self, *, owner_id: str, artifact_id: str, filename: str,
        content_type: str, contents: bytes,
    ) -> StoredObject:
        name = self.object_name(owner_id, artifact_id, filename)
        blob = self.bucket.blob(name)
        blob.cache_control = "private, no-store"
        blob.metadata = {
            "artifact_id": artifact_id,
            "owner_id": owner_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            blob.upload_from_string(contents, content_type=content_type, if_generation_match=0)
            blob.reload()
        except Exception as exc:  # provider errors are normalized at the boundary
            raise ArtifactStorageError("Private artifact upload failed.") from exc
        return StoredObject(name, len(contents), blob.generation)

    def get(self, object_name: str) -> bytes:
        try:
            return self.bucket.blob(object_name).download_as_bytes()
        except Exception as exc:
            raise ArtifactStorageError("Private artifact download failed.") from exc

    def delete(self, object_name: str) -> None:
        try:
            self.bucket.blob(object_name).delete()
        except Exception as exc:
            if getattr(exc, "code", None) != 404:
                raise ArtifactStorageError("Private artifact deletion failed.") from exc
