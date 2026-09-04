"""Synthetic Google storage binding tests; no credentials or provider calls."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gcs_object_store import ProviderExceptions
from google_storage_binding import (
    BucketNamespaceVerifier,
    ProfileStorageConfig,
    bind_google_storage,
)


class Missing(Exception):
    pass


class Conflict(Exception):
    pass


class Unavailable(Exception):
    pass


ERRORS = ProviderExceptions((Missing,), (Conflict,), (Unavailable,))
OWNER_ID = "290ac58e-98db-4f31-b026-2969e65f0d80"


class Blob:
    generation = None

    def reload(self, **kwargs):
        raise Missing

    def download_to_file(self, *args, **kwargs):
        raise AssertionError("An absent object must not be downloaded.")

    def upload_from_string(self, *args, **kwargs):
        raise AssertionError("Binding must not write storage.")


class Bucket:
    def __init__(self):
        self.bound_names = []
        self.reload_calls = []
        self.bound_blob = Blob()

    def blob(self, name):
        self.bound_names.append(name)
        return self.bound_blob

    def reload(self, **kwargs):
        self.reload_calls.append(kwargs)


class Client:
    def __init__(self):
        self.bucket_names = []
        self.bound_bucket = Bucket()

    def bucket(self, name):
        self.bucket_names.append(name)
        return self.bound_bucket


def config(**changes):
    values = {
        "project_id": "li-private-123",
        "bucket_name": "li-private-profile",
        "owner_profile_id": OWNER_ID,
    }
    values.update(changes)
    return ProfileStorageConfig(**values)


def test_mapping_derives_the_only_object_name_without_accepting_a_path():
    value = ProfileStorageConfig.from_mapping({
        "LI_PROFILE_GCP_PROJECT": "li-private-123",
        "LI_PROFILE_BUCKET": "li-private-profile",
        "LI_PROFILE_OWNER_ID": OWNER_ID,
        "LI_PROFILE_OBJECT": "attacker/chosen/path",
    })
    assert value.object_name == f"profiles/{OWNER_ID}/current"
    assert OWNER_ID not in repr(value)


@pytest.mark.parametrize("changes", [
    {"project_id": "UPPERCASE"},
    {"project_id": "short"},
    {"bucket_name": "path/to/object"},
    {"bucket_name": "legacy_bucket_name"},
    {"bucket_name": "192.168.0.1"},
    {"bucket_name": "-bad-name"},
    {"owner_profile_id": "not-a-uuid"},
    {"owner_profile_id": OWNER_ID.upper()},
])
def test_config_rejects_ambiguous_or_noncanonical_bindings(changes):
    with pytest.raises(ValueError, match="configuration is invalid"):
        config(**changes)


def test_mapping_requires_every_server_owned_setting():
    with pytest.raises(ValueError, match="incomplete"):
        ProfileStorageConfig.from_mapping({})


def test_binding_passes_only_project_and_uses_derived_bucket_and_object():
    seen = []
    client = Client()

    def factory(**kwargs):
        seen.append(kwargs)
        return client

    store = bind_google_storage(config(), factory, ERRORS)
    assert seen == [{"project": "li-private-123"}]
    assert client.bucket_names == ["li-private-profile"]
    assert client.bound_bucket.bound_names == [f"profiles/{OWNER_ID}/current"]

    assert store.read() is None
    assert client.bound_bucket.reload_calls == [{"timeout": 10.0, "retry": None}]


def test_namespace_verifier_requires_and_calls_exact_bucket_probe():
    bucket = Bucket()
    verifier = BucketNamespaceVerifier(bucket)
    assert verifier.verify(timeout=4.0, retry=None) is True
    assert bucket.reload_calls == [{"timeout": 4.0, "retry": None}]
    with pytest.raises(TypeError):
        BucketNamespaceVerifier(object())


@pytest.mark.parametrize("dependency", [object(), lambda **kwargs: object()])
def test_binding_rejects_invalid_client_layers(dependency):
    with pytest.raises(TypeError):
        bind_google_storage(config(), dependency, ERRORS)
