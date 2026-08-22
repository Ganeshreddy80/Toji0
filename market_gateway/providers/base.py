"""Base provider implementation for the Market Gateway ecosystem."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.core.interfaces import IMarketGatewayProvider

logger = logging.getLogger(__name__)


class BaseGatewayProvider(IMarketGatewayProvider):
    """Abstract base class for all Market Gateway providers, implementing stats and state."""

    def __init__(self) -> None:
        self._name = "Generic"
        self._status = "disconnected"  # "connected", "disconnected", "reconnecting", "degraded"
        self._last_heartbeat: datetime | None = None
        self._reconnect_count = 0
        self._dropped_messages = 0
        self._latency_ms = 0.0
        self._last_update: datetime | None = None
        self._queue_length = 0
        self._initialized = False

    @property
    def name(self) -> str:
        return self._name

    def initialize(self) -> None:
        if self._initialized:
            return
        logger.info("Initializing provider: %s", self.name)
        self._status = "disconnected"
        self._do_initialize()
        self._initialized = True

    def shutdown(self) -> None:
        if not self._initialized:
            return
        logger.info("Shutting down provider: %s", self.name)
        self._do_shutdown()
        self._initialized = False
        self._status = "disconnected"

    def check_health(self) -> dict[str, Any]:
        """Return connectivity stats and status metrics."""
        return {
            "status": self._status,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "reconnect_count": self._reconnect_count,
            "dropped_messages": self._dropped_messages,
            "latency_ms": self._latency_ms,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "queue_length": self._queue_length,
        }

    # Stubs/hooks for subclass extension
    def _do_initialize(self) -> None:
        pass

    def _do_shutdown(self) -> None:
        pass

    def subscribe_candles(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        raise NotImplementedError

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        raise NotImplementedError

    def subscribe_order_book(
        self, symbol: str, callback: Callable[[OrderBookSnapshot], None]
    ) -> None:
        raise NotImplementedError

    def get_historical_candles(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        raise NotImplementedError

    def get_exchange_info(self) -> dict[str, Any]:
        return {}

    def get_symbols(self) -> list[str]:
        return []
