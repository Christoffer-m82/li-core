import json
import struct
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import SPECIALISTS, app


ROOT = Path(__file__).parents[1]
client = TestClient(app)
ELENA_HASH = "eeef7b0c7497054e9593d1ef41cd59bac148ae8c084758455b61db87013d4d74"
SYSTEM_PORTRAIT_HASHES = {
    "ada": "e9e3b12a069e053820b7ee9ba0dff6bc2d5676e9da5e66d0d5d62ca9ef94751e",
    "theo": "56381041c2c9f3f4c6cc239f2fae53d673d598c23165b84b5d67292bb6615caa",
    "heimdall": "5b0b11e64a30e451304548add5940fd6dbfd517cd1f9df24fa45a9c7b7acaa68",
}


def test_every_specialist_has_a_served_portrait_and_canonical_elena():
    import hashlib

    asset_dir = ROOT / "static" / "assets" / "portraits"
    names = {item["id"] for item in SPECIALISTS} | SYSTEM_PORTRAIT_HASHES.keys()
    assert {path.stem for path in asset_dir.glob("*.png")} == names
    for name in names:
        asset = asset_dir / f"{name}.png"
        assert png_dimensions(asset) == (1254, 1254)
        response = client.get(f"/assets/portraits/{name}.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == asset.read_bytes()
    # Locks in the owner's selected Elena without putting revision labels in the UI.
    assert hashlib.sha256((asset_dir / "elena.png").read_bytes()).hexdigest() == ELENA_HASH
    for name, expected in SYSTEM_PORTRAIT_HASHES.items():
        assert hashlib.sha256((asset_dir / f"{name}.png").read_bytes()).hexdigest() == expected


def test_system_agent_profiles_preserve_registry_roles_and_specialist_separation():
    import re

    script = (ROOT / "static/assets/app.js").read_text(encoding="utf-8")
    registry = (ROOT.parent / "agents/registry.yaml").read_text(encoding="utf-8")
    for key in SYSTEM_PORTRAIT_HASHES:
        match = re.search(rf'  {key}:\s+name: "([^"]+)"\s+type: "system"\s+role: "([^"]+)"', registry)
        assert match
        assert f"id: '{key}', name: '{match[1]}', role: '{match[2]}'" in script
    assert not (set(SYSTEM_PORTRAIT_HASHES) & {item["id"] for item in SPECIALISTS})
    html = client.get("/").text
    assert 'id="home-system-agents"' not in html
    assert "#home-system-agents" not in script
    for location in ("directory-system-agents", "backend-system-agents"):
        assert f'id="{location}"' in html
    assert "not proof of current activity" in html


def test_home_welcome_is_inside_chat_header_without_standalone_banner():
    html = client.get("/").text
    home = html.split('data-view-panel="home">', 1)[1].split('</section>', 1)[0]
    heading = home.split('class="conversation-heading">', 1)[1].split('id="messages"', 1)[0]
    assert 'home-orb-stage' not in home
    assert 'System agents' not in home
    for text in (
        'LI IS READY',
        'What can we work through?',
        'One private conversation, with specialists brought in only when useful.',
    ):
        assert text in heading
        assert home.count(text) == 1
    for control in ('li-state-label', 'voice-output-toggle', 'stop-speaking'):
        assert f'id="{control}"' in heading


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_home_chat_can_shrink_and_preserves_touch_targets():
    css = (ROOT / "static/assets/app.css").read_text(encoding="utf-8")
    assert '.conversation-panel{grid-template-columns:minmax(0,1fr)}' in css
    assert '.composer textarea{min-width:0}' in css
    assert '.composer button{flex:0 0 44px;width:44px;height:44px}' in css
    assert '.voice-output-controls .icon-button{width:44px;height:44px}' in css


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

    assert "li-shell-v13" in service_worker


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


def test_appearance_assets_and_creator_are_available_without_external_fonts():
    html = client.get("/").text
    worker = client.get("/sw.js").text
    for asset in ("/assets/themes.js", "/assets/appearance.css"):
        assert client.get(asset).status_code == 200
        assert asset in html and asset in worker
    assert html.index('src="/assets/themes.js"') < html.index('src="/assets/app.js"')
    assert 'id="theme-library"' in html and 'id="theme-editor"' in html
    assert 'id="theme-editor-status" role="status" aria-live="polite"' in html
    assert "fonts.googleapis.com" not in html
