"""Application-boundary tests use synthetic identities, streams and photo bytes only."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_application import ProfileAccessDenied, ProfileApplication, VerifiedWorkloadIdentity
from profile_state import ProfileConflict, ProfileState, Snapshot
from upload_input import UnsupportedUpload


PHOTO = b"\xff\xd8normalized-synthetic-photo\xff\xd9"
GOOD = VerifiedWorkloadIdentity("profile-service", "frontend-bff")


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
    def __init__(self):
        self.calls = []

    async def normalize(self, upload):
        self.calls.append(upload)
        return PHOTO


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


def application(snapshot=None):
    repository = Repository(snapshot)
    decoder = Decoder()
    return ProfileApplication(
        ProfileState(repository), decoder,
        expected_audience="profile-service", allowed_subject="frontend-bff",
    ), repository, decoder


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    def test_configuration_and_dependency_validation(self):
        state = ProfileState(Repository())
        with self.assertRaises(TypeError):
            ProfileApplication(object(), Decoder(), expected_audience="a", allowed_subject="s")
        with self.assertRaises(TypeError):
            ProfileApplication(state, object(), expected_audience="a", allowed_subject="s")
        for value in ("", "å", "x" * 513):
            with self.assertRaises(ValueError):
                ProfileApplication(state, Decoder(), expected_audience=value, allowed_subject="s")

    def test_metadata_and_image_are_owner_bound_by_injected_repository(self):
        snapshot = Snapshot("00000000-0000-0000-0000-000000000001", PHOTO)
        app, repository, _ = application(snapshot)
        self.assertEqual(app.metadata(GOOD), snapshot.metadata())
        self.assertEqual(app.image(GOOD), PHOTO)
        self.assertEqual(repository.reads, 2)

    async def test_wrong_workload_is_rejected_before_storage_stream_or_decoder(self):
        for caller in (
            None,
            VerifiedWorkloadIdentity("wrong-audience", "frontend-bff"),
            VerifiedWorkloadIdentity("profile-service", "backend-runtime"),
        ):
            app, repository, decoder = application()
            stream = Stream(b"\xff\xd8\xffsynthetic")
            with self.assertRaises(ProfileAccessDenied):
                app.metadata(caller)
            with self.assertRaises(ProfileAccessDenied):
                app.image(caller)
            with self.assertRaises(ProfileAccessDenied):
                app.remove(caller, expected_revision="absent")
            with self.assertRaises(ProfileAccessDenied):
                await app.replace(caller, stream, media_type="image/jpeg",
                                  declared_file_length=None, expected_revision="absent")
            self.assertFalse(stream.started)
            self.assertEqual(repository.reads, 0)
            self.assertEqual(decoder.calls, [])

    async def test_replace_collects_decodes_and_commits_without_owner_input(self):
        app, repository, decoder = application()
        stream = Stream(b"\x89PNG\r\n\x1a\n", b"synthetic")
        result = await app.replace(
            GOOD, stream, media_type="image/png", declared_file_length="17",
            expected_revision="absent",
        )
        self.assertEqual(result["state"], "available")
        self.assertEqual(repository.snapshot.photo, PHOTO)
        self.assertEqual(repository.writes, 1)
        self.assertEqual(decoder.calls[0].media_type, "image/png")

    async def test_stale_revision_is_rejected_before_stream_and_decoder(self):
        snapshot = Snapshot("00000000-0000-0000-0000-000000000001", PHOTO)
        app, repository, decoder = application(snapshot)
        stream = Stream(b"\xff\xd8\xffsynthetic")
        with self.assertRaises(ProfileConflict):
            await app.replace(GOOD, stream, media_type="image/jpeg",
                              declared_file_length=None, expected_revision="absent")
        self.assertFalse(stream.started)
        self.assertEqual(repository.reads, 1)
        self.assertEqual(repository.writes, 0)
        self.assertEqual(decoder.calls, [])

    async def test_invalid_upload_never_reaches_decoder_or_storage_write(self):
        app, repository, decoder = application()
        with self.assertRaises(UnsupportedUpload):
            await app.replace(GOOD, Stream(b"GIF89a"), media_type="image/gif",
                              declared_file_length=None, expected_revision="absent")
        self.assertEqual(repository.writes, 0)
        self.assertEqual(decoder.calls, [])

    def test_remove_preserves_revision_rules(self):
        snapshot = Snapshot("00000000-0000-0000-0000-000000000001", PHOTO)
        app, repository, _ = application(snapshot)
        result = app.remove(GOOD, expected_revision=snapshot.revision)
        self.assertEqual(result["state"], "empty")
        self.assertIsNone(repository.snapshot.photo)


if __name__ == "__main__":
    unittest.main()
