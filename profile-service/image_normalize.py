"""Decoder core for an isolated worker. Never run inline in an HTTP request process.

The worker's CPU/memory/concurrency sandbox remains an integration requirement.
Local tests use generated fixtures only; this module alone is not an upload service.
"""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from profile_state import MAX_PHOTO_BYTES, InvalidPhoto
from upload_input import MAX_INPUT_BYTES, EncodedUpload

MAX_PIXELS = 16_000_000
MAX_AXIS = 8192
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def _check_image(image: Image.Image, expected: str) -> None:
    width, height = image.size
    if (
        image.format != expected or width < 1 or height < 1
        or max(width, height) > MAX_AXIS or width * height > MAX_PIXELS
        or getattr(image, "n_frames", 1) != 1
        or getattr(image, "is_animated", False)
    ):
        raise InvalidPhoto("Unsupported image dimensions, format or animation.")


def normalize(upload: EncodedUpload) -> bytes:
    """Center-square crop after EXIF orientation; UI must preview this same crop.

    Returns a 512x512 RGB JPEG. No originals or metadata are written to disk.
    A fresh pixel-only image prevents info dictionaries surviving re-encoding.
    """
    if (
        not isinstance(upload, EncodedUpload)
        or not isinstance(upload.media_type, str) or upload.media_type not in FORMATS
        or not isinstance(upload.contents, bytes) or not 1 <= len(upload.contents) <= MAX_INPUT_BYTES
    ):
        raise InvalidPhoto("Invalid encoded image.")
    expected = FORMATS[upload.media_type]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(upload.contents), formats=[expected]) as probe:
                _check_image(probe, expected)
                probe.verify()
            with Image.open(BytesIO(upload.contents), formats=[expected]) as source:
                _check_image(source, expected)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                try:
                    with (
                        oriented.convert("RGBA") as rgba,
                        ImageOps.fit(rgba, (512, 512), method=Image.Resampling.LANCZOS) as crop,
                        Image.new("RGB", (512, 512), "white") as clean,
                        crop.getchannel("A") as alpha,
                    ):
                        clean.paste(crop, mask=alpha)
                        output = BytesIO()
                        clean.save(output, format="JPEG", quality=85, exif=b"", icc_profile=None)
                        result = output.getvalue()
                finally:
                    oriented.close()
        if len(result) > MAX_PHOTO_BYTES:
            raise InvalidPhoto("Normalized image exceeds the profile size limit.")
        return result
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise InvalidPhoto("Image could not be safely processed.") from None
