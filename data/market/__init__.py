"""Market data ingestion and event bus distribution coordinator."""

from __future__ import annotations

import logging
from typing import Any

from toji_platform.core.event_bus import IEventBus
from toji_platform.core.event_bus.events import MarketDataUpdated

logger = logging.getLogger(__name__)


class MarketDataCoordinator:
    """Manages active subscriptions with providers and publishes to Kernel Event Bus."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._active_subscriptions: set[str] = set()

    def handle_market_update(self, symbol: str, data: dict[str, Any]) -> None:
        """Triggered by providers when new price updates arrive."""
        logger.debug("Received market update for %s", symbol)

        # Broadcast onto the kernel event bus
        event = MarketDataUpdated(
            source=f"market_coordinator.{symbol}",
            payload={"symbol": symbol, "data": data},
        )
        self._event_bus.publish(event)

    def subscribe(self, symbol: str) -> None:
        """Add symbol to tracked active feed subscriptions."""
        self._active_subscriptions.add(symbol)
        logger.info("Subscribed coordinator to market feed for: %s", symbol)

    def unsubscribe(self, symbol: str) -> None:
        """Remove symbol from active feed subscriptions."""
        self._active_subscriptions.discard(symbol)
        logger.info("Unsubscribed coordinator from market feed for: %s", symbol)

    @property
    def subscriptions(self) -> list[str]:
        """List currently tracked active subscriptions."""
        return list(self._active_subscriptions)
