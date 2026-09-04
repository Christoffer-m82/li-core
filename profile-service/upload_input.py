"""Bounded file-part intake, not a decoder, multipart parser or authenticated endpoint."""

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass, field

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_CHUNKS = 8192
UPLOAD_SECONDS = 15
SUPPORTED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


class InvalidUpload(ValueError):
    """Malformed or incomplete upload; messages never contain input values."""


class UploadTooLarge(InvalidUpload):
    """Encoded file exceeds the intake budget."""


class UnsupportedUpload(InvalidUpload):
    """Declared format is unsupported or mismatches the file signature."""


@dataclass(frozen=True)
class EncodedUpload:
    """Still untrusted: must pass isolated decoding before entering ProfileState."""

    media_type: str
    contents: bytes = field(repr=False)


def _length(value: str | None) -> int | None:
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 10 or not value.isascii() or not value.isdecimal():
        raise InvalidUpload("Invalid file length.")
    size = int(value)
    if size > MAX_INPUT_BYTES:
        raise UploadTooLarge("Profile photo exceeds 5 MiB.")
    if size == 0:
        raise InvalidUpload("Profile photo is empty.")
    return size


def _signature(contents: bytearray) -> str | None:
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "image/webp"
    return None


async def collect_upload(
    chunks: AsyncIterable[bytes], media_type: str, declared_file_length: str | None = None,
) -> EncodedUpload:
    """Read one file part after authentication; never trust request Content-Length.

    The caller must separately bound multipart overhead, transport chunk allocation,
    request concurrency and connection lifetime. Translate transport failures to
    OSError without logging request bodies. declared_file_length describes only
    this file part, not the enclosing multipart request. Cancellation propagates.
    """
    if not isinstance(media_type, str) or media_type not in SUPPORTED_TYPES:
        raise UnsupportedUpload("Use JPEG, PNG or WebP.")
    expected = _length(declared_file_length)
    contents = bytearray()
    count = 0
    try:
        async with asyncio.timeout(UPLOAD_SECONDS):
            async for chunk in chunks:
                count += 1
                if count > MAX_CHUNKS or not isinstance(chunk, bytes):
                    raise InvalidUpload("Invalid upload stream.")
                size = len(contents) + len(chunk)
                if size > MAX_INPUT_BYTES:
                    raise UploadTooLarge("Profile photo exceeds 5 MiB.")
                if expected is not None and size > expected:
                    raise InvalidUpload("File length does not match upload.")
                contents.extend(chunk)
        if not contents or (expected is not None and len(contents) != expected):
            raise InvalidUpload("Empty or incomplete upload.")
        if _signature(contents) != media_type:
            raise UnsupportedUpload("File format does not match its declared type.")
        return EncodedUpload(media_type, bytes(contents))
    except InvalidUpload:
        raise
    except OSError:
        raise InvalidUpload("Upload could not be completed.") from None
    finally:
        # Release our buffer on success, failure and cancellation; not secure erasure.
        contents.clear()
