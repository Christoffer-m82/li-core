"""Private HTTP contract tests use synthetic tokens, identities and images only."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from http_contract import IdentityVerificationError, ProfileHttpContract
from profile_application import ProfileApplication, VerifiedWorkloadIdentity
from profile_state import ProfileState, Snapshot

PHOTO = b"\xff\xd8synthetic-normalized-photo\xff\xd9"
REVISION = "00000000-0000-0000-0000-000000000001"
AUTH = "Bearer synthetic.test.token"


class Repository:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.reads = 0
        self.writes = 0

    def read(self):
        self.reads += 1
        return self.snapshot

    def compare_and_swap(self, expected, replacement):
        self.writes += 1
        actual = self.snapshot.revision if self.snapshot else "absent"
        if actual != expected:
            return False
        self.snapshot = replacement
        return True


class Decoder:
    async def normalize(self, _upload):
        return PHOTO


class Verifier:
    def __init__(self, identity=None, error=False):
        self.identity = identity or VerifiedWorkloadIdentity("profile-service", "frontend-bff")
        self.error = error
        self.calls = []

    def verify(self, token, *, audience):
        self.calls.append((token, audience))
        if self.error:
            raise IdentityVerificationError("private verifier diagnostic")
        return self.identity


class Stream:
    def __init__(self, *chunks):
        self.chunks = chunks
        self.started = False

    def __aiter__(self):
        self.started = True
        return self._iterate()

    async def _iterate(self):
        for chunk in self.chunks:
            yield chunk


def contract(snapshot=None, verifier=None):
    repository = Repository(snapshot)
    verifier = verifier or Verifier()
    application = ProfileApplication(
        ProfileState(repository), Decoder(), expected_audience="profile-service",
        allowed_subject="frontend-bff",
    )
    return ProfileHttpContract(application, verifier, audience="profile-service"), repository, verifier


def body(response):
    return json.loads(response.body)


class HttpContractTests(unittest.IsolatedAsyncioTestCase):
    def assert_private(self, response):
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_metadata_and_image_contract(self):
        snapshot = Snapshot(REVISION, PHOTO)
        api, _, verifier = contract(snapshot)
        metadata = api.metadata(AUTH)
        image = api.image(AUTH)
        self.assertEqual(metadata.status, 200)
        self.assertEqual(body(metadata), snapshot.metadata())
        self.assertEqual(image.status, 200)
        self.assertEqual(image.body, PHOTO)
        self.assertEqual(image.headers["Content-Type"], "image/jpeg")
        self.assertEqual(verifier.calls, [("synthetic.test.token", "profile-service")] * 2)
        self.assert_private(metadata)
        self.assert_private(image)

    def test_empty_image_is_explicit_not_found(self):
        api, _, _ = contract()
        response = api.image(AUTH)
        self.assertEqual(response.status, 404)
        self.assertEqual(body(response)["detail"], "Profile photo is not set.")
        self.assert_private(response)

    async def test_missing_malformed_and_failed_auth_never_touch_storage_or_stream(self):
        invalid = (None, "", "bearer token", "Bearer ", "Bearer has space", "Bearer å",
                   "Bearer " + "x" * 8193)
        for authorization in invalid:
            api, repository, verifier = contract()
            stream = Stream(b"\xff\xd8\xffsynthetic")
            response = await api.replace(
                authorization, stream, content_type="image/jpeg",
                file_length=None, if_match="absent",
            )
            self.assertEqual(response.status, 401)
            self.assertFalse(stream.started)
            self.assertEqual(repository.reads, 0)
            self.assertNotIn("token", response.body.decode())
            if authorization == "Bearer å":
                self.assertEqual(verifier.calls, [])
        verifier = Verifier(error=True)
        api, repository, _ = contract(verifier=verifier)
        response = api.metadata(AUTH)
        self.assertEqual(response.status, 401)
        self.assertEqual(repository.reads, 0)
        self.assertNotIn("diagnostic", response.body.decode())

    def test_wrong_verified_workload_is_forbidden_without_storage_access(self):
        verifier = Verifier(VerifiedWorkloadIdentity("profile-service", "backend-runtime"))
        api, repository, _ = contract(verifier=verifier)
        response = api.metadata(AUTH)
        self.assertEqual(response.status, 403)
        self.assertEqual(repository.reads, 0)

    async def test_replace_and_remove_return_only_committed_metadata(self):
        api, repository, _ = contract()
        stream = Stream(b"\x89PNG\r\n\x1a\n", b"synthetic")
        replaced = await api.replace(
            AUTH, stream, content_type="image/png", file_length="17", if_match="absent",
        )
        self.assertEqual(replaced.status, 200)
        self.assertEqual(body(replaced)["state"], "available")
        self.assertEqual(repository.snapshot.photo, PHOTO)
        removed = api.remove(AUTH, if_match=body(replaced)["revision"])
        self.assertEqual(removed.status, 200)
        self.assertEqual(body(removed)["state"], "empty")
        self.assertIsNone(repository.snapshot.photo)

    async def test_known_failures_have_specific_generic_statuses(self):
        cases = (
            ({"content_type": "image/jpeg", "file_length": "6000000", "if_match": "absent"}, 413),
            ({"content_type": "image/gif", "file_length": None, "if_match": "absent"}, 415),
            ({"content_type": "image/jpeg", "file_length": None, "if_match": "bad"}, 409),
            ({"content_type": "image/jpeg", "file_length": None, "if_match": None}, 409),
        )
        for arguments, expected in cases:
            api, repository, _ = contract()
            response = await api.replace(AUTH, Stream(b"not-an-image"), **arguments)
            self.assertEqual(response.status, expected)
            self.assertEqual(repository.writes, 0)
            self.assert_private(response)

    def test_constructor_rejects_unbound_dependencies_and_bad_audience(self):
        application = ProfileApplication(
            ProfileState(Repository()), Decoder(), expected_audience="profile-service",
            allowed_subject="frontend-bff",
        )
        with self.assertRaises(TypeError):
            ProfileHttpContract(object(), Verifier(), audience="a")
        with self.assertRaises(TypeError):
            ProfileHttpContract(application, object(), audience="a")
        for audience in ("", "å", "x" * 513):
            with self.assertRaises(ValueError):
                ProfileHttpContract(application, Verifier(), audience=audience)

    def test_response_headers_are_immutable(self):
        response = contract()[0].metadata(AUTH)
        with self.assertRaises(TypeError):
            response.headers["Cache-Control"] = "public"


if __name__ == "__main__":
    unittest.main()
