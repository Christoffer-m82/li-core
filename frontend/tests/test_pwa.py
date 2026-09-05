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
    assert '.composer textarea{min-width:0;min-height:44px}' in css
    assert '.composer button{flex:0 0 44px;width:44px;height:44px}' in css
    assert '.voice-output-controls .icon-button{width:44px;height:44px}' in css


def test_primary_views_announce_context_and_preserve_touch_targets():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    css = (ROOT / "static/assets/app.css").read_text(encoding="utf-8")
    javascript = (ROOT / "static/assets/app.js").read_text(encoding="utf-8")

    assert html.count('data-view="home" aria-current="page"') == 2
    assert 'button.setAttribute(\'aria-current\', current ? \'page\' : \'false\')' in javascript
    for context in (
        "Review private proactive briefs and useful suggestions from Li.",
        "See specialist roles, measured activity, and recommendations.",
        "Work with Li and this specialist, or review recorded evidence.",
        "Manage appearance, devices, profile, voice, and privacy.",
    ):
        assert context in javascript

    for rule in (
        ".account-button{width:44px;height:44px",
        ".text-button{min-height:44px",
        ".secondary-button,.primary-button{min-height:44px",
        ".settings-panel select{min-height:44px}",
        ".analytics-toolbar select,.relevance-panel select{min-height:44px",
        ".backend-toolbar input,.backend-toolbar select{min-width:0;min-height:44px",
        ".place-setting input{width:100%;min-height:44px",
    ):
        assert rule in css

    privacy_css = (ROOT / "static/assets/privacy.css").read_text(encoding="utf-8")
    assert ".chat-attachment a { display: inline-flex; align-items: center; min-height: 44px; }" in privacy_css
    assert ".chat-attachment button, .attachment-tray button { min-height: 44px;" in privacy_css


def test_appearance_edit_transfer_controls_are_labelled_and_present():
    html = client.get("/").text
    for control in (
        "theme-edit-selected", "theme-copy-selected", "theme-export", "theme-import",
        "theme-editor-panel", "theme-editor-heading", "theme-save", "theme-editor-cancel",
    ):
        assert html.count(f'id="{control}"') == 1
    assert 'aria-describedby="theme-transfer-help"' in html
    assert 'id="theme-transfer-status" role="status" aria-live="polite"' in html
    assert "Built-in themes cannot be overwritten." in html


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

    assert "li-shell-v17" in service_worker


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


def test_profile_photo_controls_and_private_network_only_asset_are_wired():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    worker = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
    response = client.get("/")
    for control in ("profile-photo-input", "profile-photo-choose", "profile-photo-save",
                    "profile-photo-cancel", "profile-photo-remove", "profile-photo-status"):
        assert html.count(f'id="{control}"') == 1
    assert "/assets/profile-photo.js" in html and "/assets/profile-photo.js" in worker
    assert html.index('src="/assets/profile-photo.js"') < html.index('src="/assets/app.js"')
    assert "/api/profile/" not in worker
    assert "blob:" in response.headers["content-security-policy"]


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
