"""Canonical market event definitions for the Toji event pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.schemas.market_data import (
    OHLCV,
    EconomicEvent,
    FundingRate,
    Liquidation,
    NewsEvent,
    OpenInterest,
    OrderBookSnapshot,
    Trade,
)
from toji_platform.core.event_bus.events import MarketDataUpdated


@dataclass(frozen=True)
class BaseMarketEvent(MarketDataUpdated):
    """Base class for all normalized market events."""

    @property
    def event_type(self) -> str:
        """Override event_type to match the system.market_data_updated pattern.

        This ensures existing decision and dashboard orchestrators catch these events
        without modifying subscriber strings.
        """
        return "system.market_data_updated"

    @property
    def symbol(self) -> str:
        return str(self.payload.get("symbol", ""))

    @property
    def data_type(self) -> str:
        return str(self.payload.get("data_type", ""))


@dataclass(frozen=True)
class MarketCandleEvent(BaseMarketEvent):
    """Canonical event for OHLCV candles."""

    @property
    def candle(self) -> OHLCV:
        return OHLCV(**self.payload["data"])


@dataclass(frozen=True)
class MarketTradeEvent(BaseMarketEvent):
    """Canonical event for market execution trades."""

    @property
    def trade(self) -> Trade:
        return Trade(**self.payload["data"])


@dataclass(frozen=True)
class MarketOrderBookEvent(BaseMarketEvent):
    """Canonical event for L2 order book snapshots."""

    @property
    def order_book(self) -> OrderBookSnapshot:
        return OrderBookSnapshot(**self.payload["data"])


@dataclass(frozen=True)
class MarketFundingEvent(BaseMarketEvent):
    """Canonical event for perpetual contract funding rates."""

    @property
    def funding_rate(self) -> FundingRate:
        return FundingRate(**self.payload["data"])


@dataclass(frozen=True)
class MarketOpenInterestEvent(BaseMarketEvent):
    """Canonical event for derivative open interest."""

    @property
    def open_interest(self) -> OpenInterest:
        return OpenInterest(**self.payload["data"])


@dataclass(frozen=True)
class MarketLiquidationEvent(BaseMarketEvent):
    """Canonical event for trade liquidations."""

    @property
    def liquidation(self) -> Liquidation:
        return Liquidation(**self.payload["data"])


@dataclass(frozen=True)
class MarketNewsEvent(BaseMarketEvent):
    """Canonical event for sentiment news alerts."""

    @property
    def news(self) -> NewsEvent:
        return NewsEvent(**self.payload["data"])


@dataclass(frozen=True)
class MarketMacroEvent(BaseMarketEvent):
    """Canonical event for macroeconomic calendar reports."""

    @property
    def macro(self) -> EconomicEvent:
        return EconomicEvent(**self.payload["data"])
