from app.main import app

EXPECTED_ROUTES = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/health/database"),
    ("GET", "/ready"),
    ("GET", "/memory/primary-user"),
    ("POST", "/memory/explicit"),
    ("GET", "/memory/recall"),
    ("POST", "/memory/proposals"),
    ("GET", "/theo/memory/proposals"),
    ("POST", "/theo/memory/proposals/{proposal_id}/review"),
    ("POST", "/theo/memory/proposals/process-next"),
    ("POST", "/owner/memory/proposals/{proposal_id}/confirm"),
    ("POST", "/owner/agents/recommendations/{recommendation_id}/execute"),
    ("POST", "/li/chat"),
    ("POST", "/artifacts/uploads"),
    ("POST", "/artifacts/generated"),
    ("GET", "/artifacts/{artifact_id}"),
    ("POST", "/artifacts/{artifact_id}/retention"),
    ("GET", "/privacy/settings"),
    ("POST", "/privacy/settings"),
    ("GET", "/specialists/interactions"),
    ("GET", "/conversations"),
    ("GET", "/conversations/{conversation_id}"),
    ("POST", "/owner/conversations/{conversation_id}/delete"),
}


def registered_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()

    for route in app.routes:
        methods = getattr(route, "methods", None)

        if not methods:
            continue

        for method in methods:
            routes.add((method, route.path))

    return routes


def test_expected_routes_are_registered() -> None:
    routes = registered_routes()

    missing = EXPECTED_ROUTES - routes

    assert not missing, f"Missing Li OS routes: {sorted(missing)}"


def test_theo_routes_exist() -> None:
    routes = registered_routes()

    assert ("GET", "/theo/memory/proposals") in routes
    assert (
        "POST",
        "/theo/memory/proposals/{proposal_id}/review",
    ) in routes


def test_owner_confirmation_route_exists() -> None:
    routes = registered_routes()

    assert (
        "POST",
        "/owner/memory/proposals/{proposal_id}/confirm",
    ) in routes
