"""Core interfaces for the Market Gateway and its providers."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Callable

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade


class IMarketGatewayProvider(abc.ABC):
    """Unified contract for all Market Gateway data providers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g., 'Binance')."""
        pass

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize provider connections and resources."""
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Safely close connections and release resources."""
        pass

    @abc.abstractmethod
    def check_health(self) -> dict[str, Any]:
        """Check status, connection state, heartbeat, reconnects, etc."""
        pass

    @abc.abstractmethod
    def subscribe_candles(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        """Subscribe to real-time OHLCV updates."""
        pass

    @abc.abstractmethod
    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        """Subscribe to real-time individual execution trades."""
        pass

    @abc.abstractmethod
    def subscribe_order_book(
        self, symbol: str, callback: Callable[[OrderBookSnapshot], None]
    ) -> None:
        """Subscribe to real-time Order Book updates."""
        pass

    @abc.abstractmethod
    def get_historical_candles(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """Fetch historical OHLCV candles."""
        pass

    @abc.abstractmethod
    def get_exchange_info(self) -> dict[str, Any]:
        """Retrieve exchange metadata / constraints."""
        pass

    @abc.abstractmethod
    def get_symbols(self) -> list[str]:
        """Discover available symbols/markets on this exchange."""
        pass
