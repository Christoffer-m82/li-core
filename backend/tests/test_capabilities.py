from app.capabilities import build_capability_inventory, documented_routes
from app.main import app


def inventory(**overrides):
    values = {
        "system_version": "test",
        "database_available": True,
        "research_available": True,
        "calendar_available": True,
        "gmail_available": True,
        "artifact_storage_configured": True,
    }
    values.update(overrides)
    return build_capability_inventory(**values)


def test_inventory_is_read_only_secret_free_and_preserves_governance_boundaries():
    payload = inventory().model_dump(mode="json")
    encoded = str(payload).casefold()
    gmail = next(item for item in payload["capabilities"] if item["id"] == "gmail")
    governance = next(item for item in payload["capabilities"] if item["id"] == "agent-analytics")

    assert payload["read_only"] is True
    assert "sending unavailable" in " ".join(gmail["access"])
    assert "approved_pending_execution" in governance["approval"]
    assert "secret values" in " ".join(payload["privacy_posture"]).casefold()
    assert "api_token" not in encoded
    assert "refresh_token" not in encoded
    assert "password" not in encoded
    assert all("covered_routes" not in item for item in payload["capabilities"])


def test_optional_provider_status_is_grounded_in_configuration():
    payload = inventory(research_available=False, calendar_available=False, gmail_available=False)
    statuses = {item.id: item.status for item in payload.capabilities}
    assert statuses["research"] == "unavailable"
    assert statuses["calendar"] == "unavailable"
    assert statuses["gmail"] == "unavailable"


def test_every_application_route_is_represented_in_capability_manifest():
    represented = documented_routes(inventory())
    registered = {
        f"{method} {route.path}"
        for route in app.routes
        if getattr(route, "methods", None)
        and route.path not in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
        for method in route.methods
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    assert registered <= represented, f"Undocumented backend routes: {sorted(registered - represented)}"
