from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.security import require_user


def signed_in_client() -> TestClient:
    app.dependency_overrides[require_user] = lambda: "owner@example.com"
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_calendar_view_uses_read_only_governed_action(monkeypatch) -> None:
    observed = {}

    async def backend(_settings, method, path, json_body=None, authority="li"):
        observed.update(method=method, path=path, body=json_body, authority=authority)
        return httpx.Response(200, json={
            "status": "completed", "action": "calendar.search", "events": [],
            "message": "Found 0 calendar event(s).", "failed_items": 0,
        })

    monkeypatch.setattr("app.main.request_backend", backend)
    start = datetime(2030, 6, 1, tzinfo=UTC)
    response = signed_in_client().get("/api/calendar/events", params={
        "time_min": start.isoformat(), "time_max": (start + timedelta(days=42)).isoformat(),
    })
    assert response.status_code == 200
    assert observed == {
        "method": "POST", "path": "/li/actions/calendar", "authority": "li",
        "body": {
            "request": {
                "action": "calendar.search", "time_min": start.isoformat(),
                "time_max": (start + timedelta(days=42)).isoformat(), "max_results": 100,
            },
            "approved": False,
        },
    }


def test_calendar_view_rejects_unbounded_or_naive_ranges() -> None:
    client = signed_in_client()
    start = datetime(2030, 6, 1, tzinfo=UTC)
    assert client.get("/api/calendar/events", params={
        "time_min": start.isoformat(), "time_max": (start + timedelta(days=44)).isoformat(),
    }).status_code == 422
    assert client.get("/api/calendar/events", params={
        "time_min": "2030-06-01T00:00:00", "time_max": "2030-06-02T00:00:00",
    }).status_code == 422


def test_finance_routes_validate_and_forward_without_broker_credentials(monkeypatch) -> None:
    calls = []

    async def backend(_settings, method, path, json_body=None, authority="li"):
        calls.append((method, path, json_body, authority))
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.main.request_backend", backend)
    client = signed_in_client()
    assert client.get("/api/finances/portfolio?account=avanza").status_code == 200
    saved = client.post("/api/finances/holdings", json={
        "account": "crypto", "symbol": "BTC", "asset_name": "Bitcoin",
        "quantity": "0.25", "average_unit_cost": "50000", "cost_currency": "USD",
        "current_unit_price": "60000", "quote_currency": "USD",
    })
    assert saved.status_code == 200
    assert calls[0][:2] == ("GET", "/finance/portfolio?account=avanza")
    assert calls[1][0:2] == ("POST", "/finance/holdings")
    assert not {"password", "token", "wallet_address", "seed_phrase"} & calls[1][2].keys()
    invalid = client.post("/api/finances/holdings", json={
        "account": "broker", "symbol": "X", "asset_name": "X", "quantity": 1,
        "average_unit_cost": 1, "cost_currency": "SEK",
    })
    assert invalid.status_code == 422
    incomplete_quote = client.post("/api/finances/holdings", json={
        "account": "crypto", "symbol": "ETH", "asset_name": "Ethereum", "quantity": 1,
        "average_unit_cost": 1, "cost_currency": "USD", "current_unit_price": 2,
    })
    assert incomplete_quote.status_code == 422


def test_new_workspaces_and_mobile_more_navigation_are_present() -> None:
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    worker = (root / "static" / "sw.js").read_text(encoding="utf-8")
    for view in ("finances", "calendar", "more"):
        assert f'data-view-panel="{view}"' in html
    for asset in ("/assets/planning.css", "/assets/calendar.js", "/assets/finances.js"):
        assert asset in html and asset in worker
    mobile = html.split('<nav class="bottom-nav"', 1)[1]
    assert mobile.count('class="nav-item') == 5
    for label in ("Home", "Calendar", "Finances", "Agents", "More"):
        assert f"<small>{label}</small>" in mobile
    assert "Week calendar Monday to Sunday" in html
    assert "No Avanza password, wallet address, seed phrase, or trading authority" in html
