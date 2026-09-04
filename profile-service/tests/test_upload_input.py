"""Synthetic signatures only: these tests do not claim image decoder validation."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from upload_input import (
    MAX_INPUT_BYTES,
    InvalidUpload,
    UnsupportedUpload,
    UploadTooLarge,
    collect_upload,
)


async def stream(*chunks):
    for chunk in chunks:
        yield chunk


class UploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_supported_signatures_across_chunks(self):
        for media_type, fixture in [
            ("image/jpeg", b"\xff\xd8\xfffixture"),
            ("image/png", b"\x89PNG\r\n\x1a\nfixture"),
            ("image/webp", b"RIFF0000WEBPfixture"),
        ]:
            with self.subTest(media_type=media_type):
                result = await collect_upload(stream(fixture[:2], fixture[2:]), media_type, str(len(fixture)))
                self.assertEqual(result.contents, fixture)
                self.assertNotIn("fixture", repr(result))

    async def test_exact_limit_without_length(self):
        fixture = b"\xff\xd8\xff" + bytes(MAX_INPUT_BYTES - 3)
        result = await collect_upload(stream(fixture), "image/jpeg")
        self.assertEqual(len(result.contents), MAX_INPUT_BYTES)

    async def test_oversize_stops_consuming(self):
        async def oversized():
            yield bytes(MAX_INPUT_BYTES)
            yield b"x"
            self.fail("Must stop reading after the limit")
        with self.assertRaises(UploadTooLarge):
            await collect_upload(oversized(), "image/jpeg")

    async def test_invalid_length_rejected_before_read(self):
        async def unread():
            self.fail("Must reject before consuming upload")
            yield b""
        for value in ["", "0", "-1", "+4", " 4", "4,4", "4.0", "４", "9" * 100, 4, str(MAX_INPUT_BYTES + 1)]:
            with self.subTest(value=value), self.assertRaises(InvalidUpload):
                await collect_upload(unread(), "image/jpeg", value)

    async def test_misleading_length_cannot_truncate_or_extend(self):
        for value in ["2", "20"]:
            with self.assertRaises(InvalidUpload):
                await collect_upload(stream(b"\xff\xd8\xfffixture"), "image/jpeg", value)

    async def test_empty_and_non_bytes(self):
        for chunks in [(), (b"",), (None,), ("secret",), (bytearray(b"x"),)]:
            with self.subTest(chunks=chunks), self.assertRaises(InvalidUpload):
                await collect_upload(stream(*chunks), "image/jpeg")

    async def test_unsupported_types(self):
        for value in [None, [], "image/gif", "image/svg+xml", "text/html", "image/jpeg;secret=x"]:
            with self.subTest(value=value), self.assertRaises(UnsupportedUpload):
                await collect_upload(stream(b"anything"), value)

    async def test_spoofed_or_truncated_signatures(self):
        for fixture in [b"GIF89a", b"<svg/>", b"\xff\xd8", b"RIFF0000WEBP"]:
            with self.assertRaises(UnsupportedUpload):
                await collect_upload(stream(fixture), "image/jpeg")

    async def test_stream_exception_is_generic(self):
        async def broken():
            yield b"\xff\xd8\xff"
            raise OSError("private filename or token")
        with self.assertRaises(InvalidUpload) as caught:
            await collect_upload(broken(), "image/jpeg")
        self.assertNotIn("private", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    async def test_empty_chunk_flood_is_bounded(self):
        with patch("upload_input.MAX_CHUNKS", 2), self.assertRaises(InvalidUpload):
            await collect_upload(stream(b"", b"", b""), "image/jpeg")

    async def test_timeout_cancels_stream(self):
        closed = asyncio.Event()
        async def slow():
            try:
                await asyncio.sleep(10)
                yield b"unused"
            finally:
                closed.set()
        with patch("upload_input.UPLOAD_SECONDS", 0.01), self.assertRaises(InvalidUpload):
            await collect_upload(slow(), "image/jpeg")
        self.assertTrue(closed.is_set())

    async def test_caller_cancellation_propagates(self):
        started = asyncio.Event()
        async def waiting():
            started.set()
            await asyncio.sleep(10)
            yield b"unused"
        task = asyncio.create_task(collect_upload(waiting(), "image/jpeg"))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
