"""Private, calculation-only portfolio models for the owner finance workspace."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AccountKind = Literal["avanza", "crypto"]


class PortfolioHoldingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holding_id: UUID | None = None
    account: AccountKind
    symbol: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,23}$")
    asset_name: str = Field(min_length=1, max_length=120)
    quantity: Decimal = Field(gt=0, max_digits=30, decimal_places=12)
    average_unit_cost: Decimal = Field(ge=0, max_digits=30, decimal_places=8)
    cost_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    current_unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=30, decimal_places=8
    )
    quote_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"
    )

    @field_validator("symbol", "cost_currency", "quote_currency")
    @classmethod
    def uppercase_codes(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @field_validator("asset_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("asset_name cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def quote_fields_are_consistent(self) -> "PortfolioHoldingInput":
        if (self.current_unit_price is None) != (self.quote_currency is None):
            raise ValueError("current_unit_price and quote_currency must be supplied together")
        return self


class PortfolioHolding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holding_id: UUID
    account: AccountKind
    symbol: str
    asset_name: str
    quantity: Decimal
    average_unit_cost: Decimal
    cost_currency: str
    current_unit_price: Decimal | None = None
    quote_currency: str | None = None
    price_as_of: datetime | None = None
    quote_source: Literal["owner_manual"] | None = None


class CurrencyTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    market_value: Decimal
    cost_basis: Decimal
    unrealized_gain: Decimal
    unrealized_gain_percent: Decimal | None
    priced_holdings: int


class PortfolioOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holdings: list[PortfolioHolding]
    totals: list[CurrencyTotal]
    unpriced_holdings: int
    valuation_mode: Literal["owner_manual"] = "owner_manual"
    live_quotes_configured: Literal[False] = False


class HoldingArchiveConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["archive_portfolio_holding"]


def build_portfolio_overview(rows: list[dict[str, object]]) -> PortfolioOverview:
    """Calculate honest per-currency totals without inventing FX conversion."""

    holdings = [PortfolioHolding.model_validate(row) for row in rows]
    grouped: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "market_value": Decimal("0"),
            "cost_basis": Decimal("0"),
            "priced_holdings": 0,
        }
    )
    unpriced = 0
    for holding in holdings:
        if (
            holding.current_unit_price is None
            or holding.quote_currency is None
            or holding.quote_currency != holding.cost_currency
        ):
            unpriced += 1
            continue
        bucket = grouped[holding.cost_currency]
        bucket["market_value"] += holding.quantity * holding.current_unit_price
        bucket["cost_basis"] += holding.quantity * holding.average_unit_cost
        bucket["priced_holdings"] += 1

    totals: list[CurrencyTotal] = []
    for currency in sorted(grouped):
        bucket = grouped[currency]
        market_value = Decimal(bucket["market_value"])
        cost_basis = Decimal(bucket["cost_basis"])
        gain = market_value - cost_basis
        percent = None if cost_basis == 0 else gain / cost_basis * 100
        totals.append(CurrencyTotal(
            currency=currency,
            market_value=market_value,
            cost_basis=cost_basis,
            unrealized_gain=gain,
            unrealized_gain_percent=percent,
            priced_holdings=int(bucket["priced_holdings"]),
        ))

    return PortfolioOverview(holdings=holdings, totals=totals, unpriced_holdings=unpriced)
