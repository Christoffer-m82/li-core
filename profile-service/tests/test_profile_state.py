"""Synthetic state tests only. No real photographs, networking or provider SDKs."""

import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from threading import Barrier, Lock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_state import (
    ABSENT,
    MAX_PHOTO_BYTES,
    InvalidPhoto,
    ProfileConflict,
    ProfileState,
    ProfileUnavailable,
    RepositoryError,
    Snapshot,
)

PHOTO = b"\xff\xd8synthetic-not-a-decodable-photo\xff\xd9"
OTHER = b"\xff\xd8another-synthetic-fixture\xff\xd9"


class MemoryRepository:
    """Test double, never a deployed persistence fallback."""

    def __init__(self):
        self.snapshot = None
        self.lock = Lock()
        self.fail_before = False
        self.fail_after = False
        self.fail_read = False
        self.writes = 0
        self.barrier = None

    def read(self):
        if self.fail_read:
            raise RepositoryError("private provider diagnostic must not escape")
        with self.lock:
            return self.snapshot

    def compare_and_swap(self, expected, replacement):
        if self.barrier:
            self.barrier.wait(timeout=3)
        with self.lock:
            self.writes += 1
            if self.fail_before:
                raise RepositoryError("private provider diagnostic must not escape")
            current = self.snapshot.revision if self.snapshot else ABSENT
            if current != expected:
                return False
            self.snapshot = replacement
            if self.fail_after:
                raise RepositoryError("uncertain response after commit")
            return True


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepository()
        self.state = ProfileState(self.repo)

    def test_absence_is_empty_and_remove_is_noop(self):
        self.assertEqual(self.state.metadata(), {"state": "empty", "revision": ABSENT})
        self.assertIsNone(self.state.image())
        self.assertEqual(self.state.remove(ABSENT), self.state.metadata())
        self.assertEqual(self.repo.writes, 0)

    def test_create_replace_remove_and_recreate(self):
        first = self.state.replace(PHOTO, ABSENT)
        second = self.state.replace(OTHER, first["revision"])
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(self.state.image(), OTHER)
        empty = self.state.remove(second["revision"])
        self.assertEqual(empty["state"], "empty")
        self.assertNotEqual(empty["revision"], ABSENT)
        self.assertIsNone(self.state.image())
        self.assertEqual(self.state.remove(empty["revision"]), empty)
        self.state.replace(PHOTO, empty["revision"])
        self.assertEqual(self.state.image(), PHOTO)

    def test_delayed_save_cannot_revive_removed_photo(self):
        saved = self.state.replace(PHOTO, ABSENT)
        empty = self.state.remove(saved["revision"])
        for revision in [ABSENT, saved["revision"]]:
            with self.assertRaises(ProfileConflict):
                self.state.replace(OTHER, revision)
        self.assertEqual(self.state.metadata(), empty)

    def test_stale_remove_does_not_remove_new_photo(self):
        old = self.state.replace(PHOTO, ABSENT)
        current = self.state.replace(OTHER, old["revision"])
        with self.assertRaises(ProfileConflict):
            self.state.remove(old["revision"])
        self.assertEqual(self.state.metadata(), current)

    def test_invalid_revision_never_writes(self):
        for value in [None, 123, "", "../owner", "not-a-revision"]:
            with self.subTest(value=value), self.assertRaises(ProfileConflict):
                self.state.replace(PHOTO, value)
        self.assertEqual(self.repo.writes, 0)

    def test_normalized_output_boundary(self):
        for value in [None, bytearray(PHOTO), b"", b"not jpeg", b"\xff\xd8" + b"a" * MAX_PHOTO_BYTES + b"\xff\xd9"]:
            with self.subTest(kind=type(value)), self.assertRaises(InvalidPhoto):
                self.state.replace(value, ABSENT)
        self.assertEqual(self.repo.writes, 0)

    def test_snapshots_are_immutable_and_repr_omits_image(self):
        self.state.replace(PHOTO, ABSENT)
        with self.assertRaises(FrozenInstanceError):
            self.repo.snapshot.photo = OTHER
        self.assertNotIn("synthetic", repr(self.repo.snapshot))
        self.assertEqual(set(self.state.metadata()), {"state", "revision"})

    def test_invalid_stored_record_is_rejected(self):
        with self.assertRaises(ValueError):
            Snapshot("arbitrary", PHOTO)
        self.repo.snapshot = {"photo": PHOTO}
        with self.assertRaises(ProfileUnavailable):
            self.state.metadata()

    def test_read_failure_is_not_empty(self):
        self.repo.fail_read = True
        for operation in [self.state.metadata, self.state.image, lambda: self.state.remove(ABSENT)]:
            with self.assertRaises(ProfileUnavailable) as caught:
                operation()
            self.assertNotIn("diagnostic", str(caught.exception))

    def test_failure_before_write_preserves_previous(self):
        saved = self.state.replace(PHOTO, ABSENT)
        self.repo.fail_before = True
        with self.assertRaises(ProfileUnavailable):
            self.state.replace(OTHER, saved["revision"])
        self.assertEqual(self.state.image(), PHOTO)
        self.assertEqual(self.repo.writes, 2)

    def test_uncertain_write_is_not_retried_and_reconciles_by_read(self):
        self.repo.fail_after = True
        with self.assertRaises(ProfileUnavailable):
            self.state.replace(PHOTO, ABSENT)
        self.assertEqual(self.repo.writes, 1)
        self.assertEqual(self.state.metadata()["state"], "available")
        self.assertEqual(self.state.image(), PHOTO)
        with self.assertRaises(ProfileConflict):
            self.state.replace(OTHER, ABSENT)
        self.assertEqual(self.repo.writes, 1)

    def test_concurrent_creation_has_one_winner(self):
        self.repo.barrier = Barrier(2)
        def create(photo):
            try:
                self.state.replace(photo, ABSENT)
                return "saved"
            except ProfileConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, [PHOTO, OTHER]))
        self.assertCountEqual(outcomes, ["saved", "conflict"])
        self.assertIn(self.state.image(), [PHOTO, OTHER])

    def test_failed_remove_preserves_photo_and_uncertain_remove_reconciles(self):
        saved = self.state.replace(PHOTO, ABSENT)
        self.repo.fail_before = True
        with self.assertRaises(ProfileUnavailable):
            self.state.remove(saved["revision"])
        self.assertEqual(self.state.image(), PHOTO)
        self.repo.fail_before = False
        self.repo.fail_after = True
        with self.assertRaises(ProfileUnavailable):
            self.state.remove(saved["revision"])
        self.assertIsNone(self.state.image())
        self.assertNotEqual(self.state.metadata()["revision"], saved["revision"])
        with self.assertRaises(ProfileConflict):
            self.state.replace(OTHER, saved["revision"])

    def test_competing_remove_and_replace_have_one_winner(self):
        saved = self.state.replace(PHOTO, ABSENT)
        self.repo.barrier = Barrier(2)
        def mutate(action):
            try:
                if action == "remove":
                    self.state.remove(saved["revision"])
                else:
                    self.state.replace(OTHER, saved["revision"])
                return action
            except ProfileConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(mutate, ["remove", "replace"]))
        self.assertEqual(outcomes.count("conflict"), 1)
        self.assertEqual(self.state.image(), None if "remove" in outcomes else OTHER)

    def test_invalid_write_result_is_not_success(self):
        self.repo.compare_and_swap = lambda expected, replacement: None
        with self.assertRaises(ProfileUnavailable):
            self.state.replace(PHOTO, ABSENT)


if __name__ == "__main__":
    unittest.main()
