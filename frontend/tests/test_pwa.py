import json
import struct
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parents[1]
client = TestClient(app)


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_manifest_has_explicit_any_and_maskable_install_icons():
    manifest = json.loads((ROOT / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))
    icons = {(icon["sizes"], icon["purpose"]): icon for icon in manifest["icons"]}

    assert manifest["display"] == "standalone"
    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    for size, pixels in (("192x192", 192), ("512x512", 512)):
        for purpose in ("any", "maskable"):
            icon = icons[(size, purpose)]
            assert icon["type"] == "image/png"
            path = ROOT / "static" / icon["src"].removeprefix("/")
            assert png_dimensions(path) == (pixels, pixels)


def test_install_icons_are_served_and_cached_with_the_shell():
    service_worker = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")

    for filename in (
        "icon-192.png",
        "icon-512.png",
        "icon-maskable-192.png",
        "icon-maskable-512.png",
    ):
        url = f"/assets/{filename}"
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert url in service_worker

    assert "li-shell-v6" in service_worker


def test_settings_exposes_install_control_and_fallback_guidance():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "static" / "assets" / "app.js").read_text(encoding="utf-8")

    assert 'id="install-app"' in html
    assert 'id="install-status"' in html
    assert 'id="install-status" class="muted" role="status" aria-live="polite"' in html
    assert "beforeinstallprompt" in app
    assert "appinstalled" in app
    assert "display-mode: standalone" in app
    assert "Install app or Add to Home screen" in app
