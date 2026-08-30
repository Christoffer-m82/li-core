"""Li-owned typed market-data adapter boundary."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class MarketQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instrument: str
    symbol: str
    price: Decimal
    currency: str
    observed_at: datetime
    market: str | None = None
    exchange: str | None = None
    provider: str
    delayed: bool
    authority: str


class MarketDataProvider(Protocol):
    def quote(self, symbol: str, *, market: str | None = None) -> MarketQuote: ...


class MarketDataUnavailable(RuntimeError):
    pass


class UnavailableMarketDataProvider:
    def quote(self, symbol: str, *, market: str | None = None) -> MarketQuote:
        del symbol, market
        raise MarketDataUnavailable("No compliant market quote provider is configured.")
