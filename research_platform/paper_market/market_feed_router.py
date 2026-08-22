"""Event Bus feed subscriber routing incoming market ticks.
"""

from __future__ import annotations

import logging
from typing import Any
from toji_platform.core.event_bus import IEventBus
from toji_platform.core.event_bus.events import MarketDataReceived
from research_platform.paper_market.interfaces import IMarketFeedRouter
from research_platform.paper_market.market_state_cache import MarketStateCache
from research_platform.paper_market.tick_dispatcher import TickDispatcher

logger = logging.getLogger(__name__)


class MarketFeedRouter(IMarketFeedRouter):
    """Subscribes to market events and updates the state cache and tick dispatcher."""

    def __init__(self, event_bus: IEventBus, cache: MarketStateCache, dispatcher: TickDispatcher) -> None:
        self._event_bus = event_bus
        self._cache = cache
        self._dispatcher = dispatcher
        self._subscribed = False

    def start_routing(self) -> None:
        """Start listening to Event Bus market updates."""
        self._event_bus.subscribe("system.market_data_received", self._handle_event)
        self._subscribed = True
        logger.info("Market Feed Router: Subscribed to system.market_data_received events.")

    def _handle_event(self, event: Any) -> None:
        # We check payload for symbol and candle close price
        payload = getattr(event, "payload", {}) or {}
        if not payload:
            return

        symbol = payload.get("symbol")
        price = 0.0

        # Match either candle or direct price parameters
        if "candle" in payload:
            price = payload["candle"].get("close", 0.0)
        elif "price" in payload:
            price = payload.get("price", 0.0)

        if symbol and price > 0.0:
            self._cache.set_price(symbol, price)
            self._dispatcher.dispatch_tick(symbol, price)

    def stop_routing(self) -> None:
        """Unsubscribe from the event stream."""
        if self._subscribed:
            try:
                self._event_bus.unsubscribe("system.market_data_received", self._handle_event)
            except Exception as e:
                logger.error("Failed to unsubscribe feed router: %s", e)
            self._subscribed = False
        logger.info("Market Feed Router: Stopped subscription routing.")
