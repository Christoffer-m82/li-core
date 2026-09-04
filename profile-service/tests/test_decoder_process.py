"""Real subprocess lifecycle tests using synthetic byte producers, never private images."""

import asyncio
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decoder_process import DecoderProcess, DecoderUnavailable, _environment
from decoder_worker import apply_limits
from profile_state import InvalidPhoto
from upload_input import EncodedUpload

UPLOAD = EncodedUpload("image/jpeg", b"synthetic-input")
PHOTO = b"\xff\xd8synthetic-output\xff\xd9"


def command(source):
    return (sys.executable, "-I", "-c", source)


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_and_slot_reuse(self):
        decoder = DecoderProcess()
        with patch("decoder_process._command", return_value=command(
            "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(" + repr(PHOTO) + ")"
        )):
            for _ in range(2):
                self.assertEqual(await decoder.normalize(UPLOAD), PHOTO)

    async def test_invalid_input_never_spawns(self):
        with patch("decoder_process.asyncio.create_subprocess_exec") as spawn:
            for value in [None, EncodedUpload("image/svg+xml", b"x"), EncodedUpload("image/jpeg", b"")]:
                with self.assertRaises(InvalidPhoto):
                    await DecoderProcess().normalize(value)
            spawn.assert_not_called()

    async def test_worker_codes_and_diagnostics(self):
        for code, expected in [(65, InvalidPhoto), (78, DecoderUnavailable), (1, DecoderUnavailable)]:
            with patch("decoder_process._command", return_value=command(
                f"import sys; sys.stderr.write('private synthetic diagnostic'); sys.exit({code})"
            )), self.assertRaises(expected) as caught:
                await DecoderProcess().normalize(UPLOAD)
            self.assertNotIn("private", str(caught.exception))

    async def test_oversize_and_malformed_output(self):
        for output in [b"bad output", b"x" * 1025]:
            with patch("decoder_process.MAX_PHOTO_BYTES", 1024), patch(
                "decoder_process._command", return_value=command(
                    "import sys; sys.stdout.buffer.write(" + repr(output) + ")"
                )
            ), self.assertRaises(DecoderUnavailable):
                await DecoderProcess().normalize(UPLOAD)

    async def test_timeout_reaps_child_and_releases_slot(self):
        original = asyncio.create_subprocess_exec
        children = []
        async def capture(*args, **kwargs):
            process = await original(*args, **kwargs)
            children.append(process)
            return process
        decoder = DecoderProcess()
        with patch("decoder_process._command", return_value=command("import time; time.sleep(30)")), patch(
            "decoder_process.asyncio.create_subprocess_exec", side_effect=capture
        ), patch("decoder_process.DECODE_SECONDS", 0.15), self.assertRaises(DecoderUnavailable):
            await decoder.normalize(UPLOAD)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)
        self.assertFalse(decoder._busy)

    async def test_busy_cancel_and_spawn_race(self):
        original = asyncio.create_subprocess_exec
        ready = asyncio.Event()
        release = asyncio.Event()
        children = []
        async def delayed(*args, **kwargs):
            process = await original(*args, **kwargs)
            children.append(process)
            ready.set()
            await release.wait()
            return process
        decoder = DecoderProcess()
        with patch("decoder_process._command", return_value=command("import time; time.sleep(30)")), patch(
            "decoder_process.asyncio.create_subprocess_exec", side_effect=delayed
        ):
            task = asyncio.create_task(decoder.normalize(UPLOAD))
            await asyncio.wait_for(ready.wait(), 3)
            with self.assertRaises(DecoderUnavailable):
                await decoder.normalize(UPLOAD)
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(children[0].returncode)
        self.assertFalse(decoder._busy)

    async def test_spawn_failure_releases_slot(self):
        decoder = DecoderProcess()
        with patch("decoder_process._command", return_value=("nonexistent-li-decoder-executable",)), self.assertRaises(DecoderUnavailable):
            await decoder.normalize(UPLOAD)
        self.assertFalse(decoder._busy)

    async def test_real_worker_fails_closed_on_windows(self):
        if sys.platform == "linux":
            self.skipTest("Non-Linux refusal check")
        with self.assertRaises(DecoderUnavailable):
            await DecoderProcess().normalize(UPLOAD)

    async def test_real_worker_normalizes_only_with_linux_limits(self):
        if sys.platform != "linux":
            self.skipTest("Linux worker acceptance check")
        from PIL import Image

        source = io.BytesIO()
        Image.new("RGB", (24, 16), (22, 88, 144)).save(source, format="PNG")
        result = await DecoderProcess().normalize(EncodedUpload("image/png", source.getvalue()))
        self.assertTrue(result.startswith(b"\xff\xd8"))
        self.assertTrue(result.endswith(b"\xff\xd9"))
        self.assertLessEqual(len(result), 512 * 1024)

    def test_environment_does_not_inherit_secrets(self):
        with patch.dict(os.environ, {"GH_TOKEN": "synthetic", "PYTHONPATH": "untrusted", "HTTPS_PROXY": "untrusted"}):
            self.assertLessEqual(set(_environment()), {"SystemRoot"})

    def test_unsupported_limits_fail_closed(self):
        with patch("decoder_worker.sys.platform", "win32"), self.assertRaises(RuntimeError):
            apply_limits()

    def test_required_resource_limits_and_failure(self):
        resource = SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIMIT_CORE=3,
                                   RLIMIT_FSIZE=4, RLIMIT_NOFILE=5, setrlimit=Mock())
        with patch("decoder_worker.sys.platform", "linux"), patch.dict(sys.modules, {"resource": resource}):
            apply_limits()
            self.assertEqual(resource.setrlimit.call_count, 5)
            resource.setrlimit.assert_any_call(1, (512 * 1024 * 1024,) * 2)
            resource.setrlimit.assert_any_call(2, (3, 3))
            resource.setrlimit.side_effect = OSError("limits unavailable")
            with self.assertRaises(OSError):
                apply_limits()
