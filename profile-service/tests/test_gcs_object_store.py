"""GCS adapter tests use a synthetic bound blob and no provider calls."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gcs_object_store import GoogleCloudObjectStore, ProviderExceptions
from object_repository import MAX_OBJECT_BYTES, ObjectStoreError


class NotFound(Exception):
    pass


class PreconditionFailed(Exception):
    pass


class ProviderUnavailable(Exception):
    pass


ERRORS = ProviderExceptions((NotFound,), (PreconditionFailed,), (ProviderUnavailable,))


class Probe:
    def __init__(self, result=True, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def verify(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def store(blob, probe=None, **kwargs):
    return GoogleCloudObjectStore(blob, ERRORS, probe or Probe(), **kwargs)


class Blob:
    def __init__(self, generation=7, contents=b"stored-object"):
        self.generation = generation
        self.contents = contents
        self.calls = []
        self.reload_error = None
        self.download_error = None
        self.upload_error = None

    def reload(self, **kwargs):
        self.calls.append(("reload", kwargs))
        if self.reload_error:
            raise self.reload_error

    def download_to_file(self, output, **kwargs):
        self.calls.append(("download", kwargs))
        if self.download_error:
            raise self.download_error
        output.write(self.contents)

    def upload_from_string(self, contents, **kwargs):
        self.calls.append(("upload", contents, kwargs))
        if self.upload_error:
            raise self.upload_error


class GcsObjectStoreTests(unittest.TestCase):
    def test_generation_pinned_bounded_read(self):
        blob = Blob()
        stored = store(blob).read()
        self.assertEqual(stored.generation, 7)
        self.assertEqual(stored.contents, b"stored-object")
        self.assertEqual(blob.calls, [
            ("reload", {"timeout": 10.0, "retry": None}),
            ("download", {
                "raw_download": True,
                "if_generation_match": 7,
                "timeout": 10.0,
                "checksum": "auto",
                "retry": None,
                "single_shot_download": False,
            }),
        ])
        self.assertNotIn("stored-object", repr(stored))

    def test_absence_is_only_not_found_during_initial_reload(self):
        blob = Blob()
        blob.reload_error = NotFound()
        probe = Probe()
        self.assertIsNone(store(blob, probe).read())
        self.assertEqual(len(blob.calls), 1)
        self.assertEqual(probe.calls, [{"timeout": 10.0, "retry": None}])

        blob = Blob()
        blob.download_error = NotFound()
        with self.assertRaises(ObjectStoreError):
            store(blob).read()

    def test_absence_requires_separate_healthy_namespace_evidence(self):
        for probe in (Probe(False), Probe(error=ProviderUnavailable()), Probe(error=NotFound())):
            blob = Blob()
            blob.reload_error = NotFound()
            with self.assertRaises(ObjectStoreError):
                store(blob, probe).read()
            self.assertEqual(probe.calls, [{"timeout": 10.0, "retry": None}])

    def test_read_generation_race_oversize_and_provider_failure_are_generic(self):
        cases = (
            (Blob(contents=b"x" * (MAX_OBJECT_BYTES + 1)), None),
            (Blob(), PreconditionFailed()),
            (Blob(), ProviderUnavailable("private provider detail")),
        )
        for blob, error in cases:
            blob.download_error = error
            with self.assertRaises(ObjectStoreError) as raised:
                store(blob).read()
            self.assertNotIn("private provider detail", str(raised.exception))

    def test_invalid_or_missing_generation_fails_before_download(self):
        for generation in (None, "7", 0, True):
            blob = Blob(generation=generation)
            with self.assertRaises(ObjectStoreError):
                store(blob).read()
            self.assertEqual([call[0] for call in blob.calls], ["reload"])

    def test_write_uses_exact_generation_without_automatic_retry(self):
        blob = Blob()
        object_store = store(blob, timeout_seconds=4)
        self.assertTrue(object_store.write(b"replacement", if_generation=7))
        self.assertEqual(blob.calls, [
            ("upload", b"replacement", {
                "content_type": "application/octet-stream",
                "if_generation_match": 7,
                "timeout": 4.0,
                "checksum": "auto",
                "retry": None,
            }),
        ])

    def test_create_and_replace_precondition_loss_return_false(self):
        for generation in (0, 12):
            blob = Blob()
            blob.upload_error = PreconditionFailed()
            self.assertFalse(store(blob).write(
                b"replacement", if_generation=generation,
            ))
            self.assertEqual(blob.calls[0][2]["if_generation_match"], generation)

    def test_write_provider_failure_and_invalid_calls_do_not_claim_success(self):
        blob = Blob()
        blob.upload_error = ProviderUnavailable("private provider detail")
        with self.assertRaises(ObjectStoreError) as raised:
            store(blob).write(b"replacement", if_generation=7)
        self.assertNotIn("private provider detail", str(raised.exception))

        for contents, generation in ((b"", 0), (b"x" * (MAX_OBJECT_BYTES + 1), 0),
                                     (b"ok", -1), (b"ok", True)):
            blob = Blob()
            with self.assertRaises(ObjectStoreError):
                store(blob).write(contents, if_generation=generation)
            self.assertEqual(blob.calls, [])

    def test_constructor_requires_bound_blob_exception_types_and_timeout(self):
        with self.assertRaises(TypeError):
            GoogleCloudObjectStore(object(), ERRORS, Probe())
        with self.assertRaises(TypeError):
            GoogleCloudObjectStore(Blob(), object(), Probe())
        with self.assertRaises(TypeError):
            GoogleCloudObjectStore(Blob(), ERRORS, object())
        for errors in (
            ProviderExceptions,
            lambda: ProviderExceptions((), (PreconditionFailed,), (ProviderUnavailable,)),
            lambda: ProviderExceptions((NotFound,), (NotFound,), (ProviderUnavailable,)),
        ):
            with self.assertRaises(TypeError):
                errors() if callable(errors) else errors
        for timeout in (0, 61, True, "10"):
            with self.assertRaises(ValueError):
                store(Blob(), timeout_seconds=timeout)

    def test_unclassified_programming_errors_are_not_hidden(self):
        blob = Blob()
        blob.download_error = RuntimeError("synthetic programming error")
        with self.assertRaises(RuntimeError):
            store(blob).read()


if __name__ == "__main__":
    unittest.main()
