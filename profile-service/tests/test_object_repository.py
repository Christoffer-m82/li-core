"""Generation-conditioned repository tests use synthetic objects only."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from object_repository import (
    EMPTY,
    MAGIC,
    ObjectRepository,
    ObjectStoreError,
    VersionedObject,
    _encode,
)
from profile_state import RepositoryError, Snapshot


PHOTO = b"\xff\xd8synthetic-photo\xff\xd9"
REVISION = "00000000-0000-0000-0000-000000000001"
NEXT = "00000000-0000-0000-0000-000000000002"


class Store:
    def __init__(self, stored=None):
        self.stored = stored
        self.writes = []
        self.before_write = None
        self.read_error = False
        self.write_error = False
        self.result = True

    def read(self):
        if self.read_error:
            raise ObjectStoreError("private provider detail")
        return self.stored

    def write(self, contents, *, if_generation):
        if self.before_write:
            self.before_write(self)
        self.writes.append((contents, if_generation))
        if self.write_error:
            raise ObjectStoreError("uncertain private provider detail")
        if type(self.result) is not bool or not self.result:
            return self.result
        actual = self.stored.generation if self.stored else 0
        if actual != if_generation:
            return False
        self.stored = VersionedObject(actual + 1, contents)
        return True


class ObjectRepositoryTests(unittest.TestCase):
    def test_absence_and_create_if_absent(self):
        store = Store()
        repository = ObjectRepository(store)
        self.assertIsNone(repository.read())
        replacement = Snapshot(REVISION, PHOTO)
        self.assertTrue(repository.compare_and_swap("absent", replacement))
        self.assertEqual(store.writes[0][1], 0)
        self.assertEqual(repository.read(), replacement)
        self.assertNotIn(b"synthetic-photo", repr(store.stored).encode())

    def test_replace_and_tombstone_use_hidden_provider_generation(self):
        store = Store(VersionedObject(41, _encode(Snapshot(REVISION, PHOTO))))
        repository = ObjectRepository(store)
        tombstone = Snapshot(NEXT, None)
        self.assertTrue(repository.compare_and_swap(REVISION, tombstone))
        self.assertEqual(store.writes[0][1], 41)
        self.assertEqual(repository.read(), tombstone)
        self.assertTrue(store.stored.contents.endswith(EMPTY))
        self.assertNotIn("41", repository.read().metadata().values())

    def test_stale_revision_does_not_write(self):
        store = Store(VersionedObject(3, _encode(Snapshot(REVISION, PHOTO))))
        repository = ObjectRepository(store)
        self.assertFalse(repository.compare_and_swap(NEXT, Snapshot(NEXT, None)))
        self.assertEqual(store.writes, [])

    def test_generation_race_has_one_winner(self):
        store = Store(VersionedObject(7, _encode(Snapshot(REVISION, PHOTO))))
        store.before_write = lambda item: setattr(
            item, "stored", VersionedObject(8, _encode(Snapshot(NEXT, None))),
        )
        repository = ObjectRepository(store)
        self.assertFalse(repository.compare_and_swap(REVISION, Snapshot(NEXT, None)))
        self.assertEqual(repository.read().revision, NEXT)

    def test_malformed_objects_fail_closed_without_contents_in_error(self):
        malformed = (
            b"wrong",
            MAGIC + b"not-a-valid-revision" + EMPTY,
            MAGIC + REVISION.encode() + b"X",
            MAGIC + REVISION.encode() + EMPTY + b"unexpected",
        )
        for contents in malformed:
            store = Store()
            store.stored = object.__new__(VersionedObject)
            object.__setattr__(store.stored, "generation", 1)
            object.__setattr__(store.stored, "contents", contents)
            with self.assertRaisesRegex(RepositoryError, "unavailable") as caught:
                ObjectRepository(store).read()
            self.assertNotIn("unexpected", str(caught.exception))

    def test_provider_failures_and_invalid_results_are_generic(self):
        for operation in ("read", "write"):
            store = Store()
            setattr(store, f"{operation}_error", True)
            repository = ObjectRepository(store)
            with self.assertRaisesRegex(RepositoryError, "unavailable") as caught:
                if operation == "read":
                    repository.read()
                else:
                    repository.compare_and_swap("absent", Snapshot(REVISION, PHOTO))
            self.assertNotIn("private", str(caught.exception))
        store = Store()
        store.result = "yes"
        with self.assertRaises(RepositoryError):
            ObjectRepository(store).compare_and_swap("absent", Snapshot(REVISION, PHOTO))

    def test_invalid_store_records_and_dependencies_are_rejected(self):
        with self.assertRaises(TypeError):
            ObjectRepository(object())
        for value in (VersionedObject, object(), "invalid"):
            store = Store(value)
            with self.assertRaises(RepositoryError):
                ObjectRepository(store).read()
        with self.assertRaises(ValueError):
            VersionedObject(0, b"x")
        with self.assertRaises(ValueError):
            VersionedObject(True, b"x")


if __name__ == "__main__":
    unittest.main()
