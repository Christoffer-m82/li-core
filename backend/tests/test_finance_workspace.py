from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import require_api_token
from app.finance import PortfolioHoldingInput, build_portfolio_overview
from app.main import app
from app.runtime_data import RuntimeDataCapabilityUnavailable


HOLDING_ID = UUID("00000000-0000-0000-0000-000000000042")


def holding(**overrides: object) -> dict[str, object]:
    value = {
        "holding_id": HOLDING_ID,
        "account": "avanza",
        "symbol": "VOLV-B",
        "asset_name": "Volvo B",
        "quantity": Decimal("10"),
        "average_unit_cost": Decimal("250"),
        "cost_currency": "SEK",
        "current_unit_price": Decimal("275"),
        "quote_currency": "SEK",
        "price_as_of": "2026-09-07T12:00:00+00:00",
        "quote_source": "owner_manual",
    }
    value.update(overrides)
    return value


def test_portfolio_totals_are_same_currency_and_unrealized_only() -> None:
    overview = build_portfolio_overview([
        holding(),
        holding(
            holding_id=UUID("00000000-0000-0000-0000-000000000043"),
            symbol="BTC",
            account="crypto",
            asset_name="Bitcoin",
            quantity=Decimal("0.1"),
            average_unit_cost=Decimal("50000"),
            current_unit_price=Decimal("60000"),
            cost_currency="USD",
            quote_currency="USD",
        ),
        holding(
            holding_id=UUID("00000000-0000-0000-0000-000000000044"),
            symbol="ETH",
            account="crypto",
            asset_name="Ethereum",
            current_unit_price=None,
            quote_currency=None,
            price_as_of=None,
            quote_source=None,
        ),
    ])
    assert [(item.currency, item.market_value, item.unrealized_gain) for item in overview.totals] == [
        ("SEK", Decimal("2750"), Decimal("250")),
        ("USD", Decimal("6000.0"), Decimal("1000.0")),
    ]
    assert overview.unpriced_holdings == 1
    assert overview.live_quotes_configured is False


def test_portfolio_input_normalizes_codes_and_requires_complete_quote() -> None:
    value = PortfolioHoldingInput(
        account="crypto", symbol="btc", asset_name=" Bitcoin ", quantity="0.25",
        average_unit_cost="50000", cost_currency="usd", current_unit_price="60000",
        quote_currency="usd",
    )
    assert value.symbol == "BTC" and value.cost_currency == "USD"
    assert value.asset_name == "Bitcoin"
    with pytest.raises(ValidationError, match="supplied together"):
        PortfolioHoldingInput(
            account="crypto", symbol="BTC", asset_name="Bitcoin", quantity="1",
            average_unit_cost="1", cost_currency="USD", current_unit_price="2",
        )


def test_finance_endpoints_are_owner_scoped_and_truthful(monkeypatch) -> None:
    app.dependency_overrides[require_api_token] = lambda: None
    monkeypatch.setattr("app.main.list_portfolio_holdings", lambda account: [holding()])
    monkeypatch.setattr("app.main.upsert_portfolio_holding", lambda payload: holding())
    monkeypatch.setattr("app.main.archive_portfolio_holding", lambda holding_id: holding_id == HOLDING_ID)
    try:
        client = TestClient(app)
        response = client.get("/finance/portfolio?account=avanza")
        assert response.status_code == 200
        assert response.json()["live_quotes_configured"] is False
        saved = client.post("/finance/holdings", json={
            "account": "avanza", "symbol": "VOLV-B", "asset_name": "Volvo B",
            "quantity": "10", "average_unit_cost": "250", "cost_currency": "SEK",
            "current_unit_price": "275", "quote_currency": "SEK",
        })
        assert saved.status_code == 200
        assert client.post(
            f"/finance/holdings/{HOLDING_ID}/archive",
            json={"confirmation": "archive_portfolio_holding"},
        ).status_code == 200
        assert client.post(
            f"/finance/holdings/{HOLDING_ID}/archive",
            json={"confirmation": "delete"},
        ).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_missing_portfolio_migration_is_not_reported_as_an_empty_portfolio(monkeypatch) -> None:
    app.dependency_overrides[require_api_token] = lambda: None
    monkeypatch.setattr(
        "app.main.list_portfolio_holdings",
        lambda _account: (_ for _ in ()).throw(RuntimeDataCapabilityUnavailable("synthetic")),
    )
    try:
        response = TestClient(app).get("/finance/portfolio")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "Private portfolio storage is not installed."}


def test_migration_042_is_private_function_only_and_has_no_trade_authority() -> None:
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "042_private_portfolio_workspace.sql").read_text(encoding="utf-8")
    lowered = sql.lower()
    assert "migration 042 requires applied schema 0.41" in lowered
    assert "force row level security" in lowered
    assert "to li_memory_api" in lowered
    assert "backend runtime lost required portfolio execution" in lowered
    assert "backend retained direct portfolio table access" in lowered
    assert "temporary schema authority was not removed" in lowered
    assert "0.42" in sql and sql.rstrip().endswith("COMMIT;")
    assert all(term not in lowered for term in ("broker_password", "wallet_seed", "place_trade"))
