"""One-shot Linux decoder subprocess. No credentials or user-selected paths."""

import sys
from pathlib import Path


def apply_limits() -> None:
    # Windows development must fail closed, not silently decode without limits.
    if sys.platform != "linux":
        raise RuntimeError("Resource-limited decoder requires Linux.")
    import resource

    for kind, value in [
        (resource.RLIMIT_AS, 512 * 1024 * 1024),
        (resource.RLIMIT_CPU, 3),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_NOFILE, 32),
    ]:
        resource.setrlimit(kind, (value, value))


def main() -> int:
    try:
        apply_limits()
    except (ImportError, OSError, ValueError, RuntimeError):
        return 78
    # -I omits the script directory; only this operator-controlled directory is added.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from image_normalize import normalize
    from profile_state import InvalidPhoto
    from upload_input import MAX_INPUT_BYTES, EncodedUpload

    if len(sys.argv) != 2 or sys.argv[1] not in {"image/jpeg", "image/png", "image/webp"}:
        return 65
    try:
        payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if not payload or len(payload) > MAX_INPUT_BYTES:
            return 65
        output = normalize(EncodedUpload(sys.argv[1], payload))
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except (InvalidPhoto, OSError, MemoryError):
        return 65


if __name__ == "__main__":
    sys.exit(main())
