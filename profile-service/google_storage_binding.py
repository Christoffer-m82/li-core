"""Strict configuration and SDK binding for one private owner-profile object.

The production constructor uses Application Default Credentials only when it is explicitly called.
Tests inject a client factory and make no credential, metadata-server or provider request.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from gcs_object_store import GoogleCloudObjectStore, ProviderExceptions

PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


@dataclass(frozen=True)
class ProfileStorageConfig:
    """Non-secret deployment settings; the object name is always server-derived."""

    project_id: str = field(repr=False)
    bucket_name: str = field(repr=False)
    owner_profile_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not PROJECT_ID.fullmatch(self.project_id):
            raise ValueError("Profile storage configuration is invalid.")
        if not isinstance(self.bucket_name, str) or not BUCKET_NAME.fullmatch(self.bucket_name):
            raise ValueError("Profile storage configuration is invalid.")
        if not isinstance(self.owner_profile_id, str):
            raise ValueError("Profile storage configuration is invalid.")
        try:
            parsed = UUID(self.owner_profile_id)
        except ValueError:
            raise ValueError("Profile storage configuration is invalid.") from None
        if str(parsed) != self.owner_profile_id:
            raise ValueError("Profile storage configuration is invalid.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> ProfileStorageConfig:
        if not isinstance(values, Mapping):
            raise TypeError("Profile storage settings are invalid.")
        try:
            return cls(
                project_id=values["LI_PROFILE_GCP_PROJECT"],
                bucket_name=values["LI_PROFILE_BUCKET"],
                owner_profile_id=values["LI_PROFILE_OWNER_ID"],
            )
        except KeyError:
            raise ValueError("Profile storage configuration is incomplete.") from None

    @property
    def object_name(self) -> str:
        return f"profiles/{self.owner_profile_id}/current"


class BucketNamespaceVerifier:
    """Prove the configured bucket is reachable before treating object 404 as absence."""

    def __init__(self, bucket: object) -> None:
        if not callable(getattr(bucket, "reload", None)):
            raise TypeError("Profile storage bucket is invalid.")
        self._bucket = bucket

    def verify(self, *, timeout: float, retry: None) -> bool:
        self._bucket.reload(timeout=timeout, retry=retry)
        return True


def bind_google_storage(
    config: ProfileStorageConfig,
    client_factory: Callable[..., Any],
    exceptions: ProviderExceptions,
) -> GoogleCloudObjectStore:
    """Bind one injected SDK client to the derived object without provider calls."""

    if not isinstance(config, ProfileStorageConfig) or not callable(client_factory):
        raise TypeError("Profile storage binding is invalid.")
    if not isinstance(exceptions, ProviderExceptions):
        raise TypeError("Profile storage binding is invalid.")
    client = client_factory(project=config.project_id)
    if not callable(getattr(client, "bucket", None)):
        raise TypeError("Profile storage client is invalid.")
    bucket = client.bucket(config.bucket_name)
    if not callable(getattr(bucket, "blob", None)):
        raise TypeError("Profile storage bucket is invalid.")
    blob = bucket.blob(config.object_name)
    return GoogleCloudObjectStore(blob, exceptions, BucketNamespaceVerifier(bucket))


def from_google_cloud(config: ProfileStorageConfig) -> GoogleCloudObjectStore:
    """Construct the real binding with ADC only during separately approved server startup."""

    try:
        from google.api_core.exceptions import (
            GoogleAPICallError,
            NotFound,
            PreconditionFailed,
            RetryError,
        )
        from google.cloud.storage import Client
    except ImportError:
        raise RuntimeError("Google profile storage is unavailable.") from None
    exceptions = ProviderExceptions(
        not_found=(NotFound,),
        precondition_failed=(PreconditionFailed,),
        unavailable=(GoogleAPICallError, RetryError),
    )
    return bind_google_storage(config, Client, exceptions)
