"""Abstract provider interfaces for market and alternative data streams."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Callable

from data.schemas.market_data import (
    OHLCV,
    EconomicEvent,
    NewsEvent,
    Trade,
)
from toji_platform.core.types import HealthStatus


class IProvider(abc.ABC):
    """Base interface for all data providers in the Toji ecosystem."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the data provider (e.g. 'Binance')."""

    @abc.abstractmethod
    def initialize(self, kernel: Any) -> None:
        """Bootstrap provider dependencies, setups connection pools or clients."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Close websocket channels, clients, database sessions safely."""

    @abc.abstractmethod
    def health_check(self) -> HealthStatus:
        """Run connectivity check probe, reporting status."""


class IMarketDataProvider(IProvider):
    """Interface for high-frequency transactional and order-book market data."""

    @abc.abstractmethod
    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        """Subscribe to real-time individual execution trade feed."""

    @abc.abstractmethod
    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        """Subscribe to real-time candle bar updates."""

    @abc.abstractmethod
    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """Fetch historical candle bars over a specific timeframe."""


class IAlternativeDataProvider(IProvider):
    """Interface for sentiment, macroeconomics, news, and external indicators."""

    @abc.abstractmethod
    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        """Retrieve recent market news events, optionally filtered by symbol."""

    @abc.abstractmethod
    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        """Fetch macroeconomic data reports scheduled over date window."""
