"""Generated in-memory images only. Requires the pinned optional decoder environment."""

import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from PIL import Image
except ImportError:
    raise unittest.SkipTest("Install requirements-decoder.txt to run decoder tests") from None

from image_normalize import normalize
from profile_state import MAX_PHOTO_BYTES, InvalidPhoto
from upload_input import EncodedUpload


def encoded(mode="RGB", size=(32, 48), color="red", format="PNG", **options):
    with Image.new(mode, size, color) as image:
        output = BytesIO()
        image.save(output, format=format, **options)
        return EncodedUpload({"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[format], output.getvalue())


class DecoderTests(unittest.TestCase):
    def test_all_formats_become_bounded_rgb_jpeg(self):
        for format in ["PNG", "JPEG", "WEBP"]:
            with self.subTest(format=format):
                result = normalize(encoded(format=format))
                self.assertLessEqual(len(result), MAX_PHOTO_BYTES)
                with Image.open(BytesIO(result)) as image:
                    image.load()
                    self.assertEqual((image.format, image.mode, image.size), ("JPEG", "RGB", (512, 512)))

    def test_metadata_is_stripped(self):
        exif = Image.Exif()
        exif[270] = "private synthetic description"
        exif[315] = "synthetic owner"
        result = normalize(encoded(format="JPEG", exif=exif, comment=b"private synthetic comment", icc_profile=b"synthetic ICC"))
        self.assertNotIn(b"synthetic", result)
        with Image.open(BytesIO(result)) as image:
            self.assertFalse(image.getexif())
            for key in ["comment", "exif", "icc_profile", "xmp"]:
                self.assertNotIn(key, image.info)

    def test_transparency_composites_white(self):
        with Image.open(BytesIO(normalize(encoded(mode="RGBA", color=(0, 0, 0, 0))))) as image:
            self.assertEqual(image.getpixel((256, 256)), (255, 255, 255))

    def test_exif_orientation_precedes_crop(self):
        with Image.new("RGB", (32, 32), "red") as image:
            image.paste("blue", (16, 0, 32, 32))
            exif = Image.Exif()
            exif[274] = 6
            buf = BytesIO()
            image.save(buf, format="PNG", exif=exif)
        with Image.open(BytesIO(normalize(EncodedUpload("image/png", buf.getvalue())))) as result:
            top, bottom = result.getpixel((256, 50)), result.getpixel((256, 460))
            self.assertGreater(top[0], top[2])
            self.assertGreater(bottom[2], bottom[0])

    def test_center_square_crop(self):
        with Image.new("RGB", (96, 32), "red") as image:
            image.paste("blue", (32, 0, 64, 32))
            buf = BytesIO()
            image.save(buf, format="PNG")
        with Image.open(BytesIO(normalize(EncodedUpload("image/png", buf.getvalue())))) as result:
            self.assertGreater(result.getpixel((256, 256))[2], 240)

    def test_animation_rejected(self):
        with Image.new("RGB", (8, 8), "red") as first, Image.new("RGB", (8, 8), "blue") as second:
            for format in ["PNG", "WEBP"]:
                output = BytesIO()
                first.save(output, format=format, save_all=True, append_images=[second], duration=100)
                with self.assertRaises(InvalidPhoto):
                    normalize(EncodedUpload("image/" + format.lower(), output.getvalue()))

    def test_bad_bytes_and_mime_mismatch(self):
        good = encoded()
        for upload in [None, EncodedUpload("image/png", b"private nonsense"),
                       EncodedUpload("image/jpeg", good.contents), EncodedUpload("image/png", good.contents[:40])]:
            with self.assertRaises(InvalidPhoto) as caught:
                normalize(upload)
            self.assertNotIn("private", str(caught.exception))

    def test_axis_limit(self):
        with self.assertRaises(InvalidPhoto):
            normalize(encoded(size=(8193, 1)))

    def test_pixel_limit_before_decode(self):
        with patch("image_normalize.MAX_PIXELS", 100), self.assertRaises(InvalidPhoto):
            normalize(encoded(size=(11, 10)))

    def test_output_budget_enforced(self):
        with patch("image_normalize.MAX_PHOTO_BYTES", 1), self.assertRaises(InvalidPhoto):
            normalize(encoded())
