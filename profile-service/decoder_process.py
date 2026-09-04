"""Async process supervision; resource limits are enforced inside decoder_worker.

One instance per service event loop. This is not a filesystem/network sandbox.
No live HTTP endpoint may enable this until the remaining isolation gates pass.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from profile_state import MAX_PHOTO_BYTES, InvalidPhoto, check_normalized
from upload_input import MAX_INPUT_BYTES, SUPPORTED_TYPES, EncodedUpload

DECODE_SECONDS = 8


class DecoderUnavailable(Exception):
    """Busy, unsupported host, crashed worker or unavailable process runtime."""


def _command(media_type: str) -> tuple[str, ...]:
    return (sys.executable, "-I", str(Path(__file__).with_name("decoder_worker.py")), media_type)


def _environment() -> dict[str, str]:
    # Do not inherit provider tokens, proxy variables, HOME or Python import overrides.
    return {"SystemRoot": os.environ["SystemRoot"]} if os.name == "nt" and "SystemRoot" in os.environ else {}


async def _finish(process, tasks) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await process.wait()


async def _cleanup_without_interruption(awaitable) -> None:
    task = asyncio.create_task(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


class DecoderProcess:
    def __init__(self) -> None:
        self._busy = False

    async def normalize(self, upload: EncodedUpload) -> bytes:
        if (
            not isinstance(upload, EncodedUpload)
            or not isinstance(upload.media_type, str) or upload.media_type not in SUPPORTED_TYPES
            or not isinstance(upload.contents, bytes) or not 1 <= len(upload.contents) <= MAX_INPUT_BYTES
        ):
            raise InvalidPhoto("Invalid encoded image.")
        if self._busy:
            raise DecoderUnavailable("Photo processing is busy. Try again shortly.")
        self._busy = True
        process = None
        tasks = []
        # Capture spawn completion even if the requester cancels during process creation.
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *_command(upload.media_type), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=_environment(), cwd=str(Path(__file__).resolve().parent),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ))
        try:
            async with asyncio.timeout(DECODE_SECONDS):
                process = await asyncio.shield(spawn)

                async def write() -> None:
                    try:
                        process.stdin.write(upload.contents)
                        await process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        process.stdin.close()

                async def read() -> bytes:
                    data = bytearray()
                    while len(data) <= MAX_PHOTO_BYTES:
                        chunk = await process.stdout.read(min(65536, MAX_PHOTO_BYTES + 1 - len(data)))
                        if not chunk:
                            return bytes(data)
                        data.extend(chunk)
                    raise DecoderUnavailable("Photo processing returned invalid output.")

                tasks = [asyncio.create_task(write()), asyncio.create_task(read()),
                         asyncio.create_task(process.wait())]
                _, result, code = await asyncio.gather(*tasks)
                if code == 65:
                    raise InvalidPhoto("Image could not be safely processed.")
                if code != 0:
                    raise DecoderUnavailable("Photo processing is unavailable.")
                try:
                    check_normalized(result)
                except InvalidPhoto:
                    raise DecoderUnavailable("Photo processing returned invalid output.") from None
                return result
        except (OSError, TimeoutError):
            raise DecoderUnavailable("Photo processing is unavailable or timed out.") from None
        finally:
            async def cleanup() -> None:
                try:
                    spawned = process if process is not None else await spawn
                except OSError:
                    return
                await _finish(spawned, tasks)
            try:
                await _cleanup_without_interruption(cleanup())
            finally:
                self._busy = False
