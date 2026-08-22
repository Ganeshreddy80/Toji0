"""Simulated Market Data Adapter for Sprint 9B (100% simulated, zero broker APIs)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple

from paper_trading.models.market_models import MarketTick, OrderBookSnapshot

logger = logging.getLogger(__name__)


class MarketDataAdapter:
    """Thread-safe simulated market data feed generator.

    MUST NEVER connect to live exchanges, send network requests, or invoke broker APIs.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribed_symbols: Set[str] = set()
        self._last_prices: Dict[str, float] = {}

    def subscribe(self, symbol: str) -> None:
        """Subscribe to simulated market ticks for symbol."""
        with self._lock:
            self._subscribed_symbols.add(symbol)
            logger.debug("Subscribed to symbol: %s", symbol)

    def unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from simulated market ticks for symbol."""
        with self._lock:
            self._subscribed_symbols.discard(symbol)
            logger.debug("Unsubscribed from symbol: %s", symbol)

    def is_subscribed(self, symbol: str) -> bool:
        """Check if symbol is currently subscribed."""
        with self._lock:
            return symbol in self._subscribed_symbols

    def get_subscribed_symbols(self) -> List[str]:
        """List all currently subscribed symbols."""
        with self._lock:
            return sorted(list(self._subscribed_symbols))

    def generate_tick(
        self,
        symbol: str,
        price: float,
        volume: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> MarketTick:
        """Generate a simulated MarketTick object for testing/feed simulation."""
        if price <= 0.0:
            raise ValueError(f"Price must be positive, got {price}")
        if volume < 0.0:
            raise ValueError(f"Volume must be non-negative, got {volume}")

        ts = timestamp or datetime.now(timezone.utc)
        tick = MarketTick(symbol=symbol, price=price, volume=volume, timestamp=ts)

        with self._lock:
            self._last_prices[symbol] = price
            return tick

    def generate_order_book(
        self,
        symbol: str,
        bids: Optional[List[Tuple[float, float]]] = None,
        asks: Optional[List[Tuple[float, float]]] = None,
        timestamp: Optional[datetime] = None,
    ) -> OrderBookSnapshot:
        """Generate a simulated OrderBookSnapshot for symbol."""
        ts = timestamp or datetime.now(timezone.utc)
        current_price = self._last_prices.get(symbol, 100.0)

        default_bids = [(round(current_price * 0.999 - i * 0.1, 2), 1.5 + i) for i in range(5)]
        default_asks = [(round(current_price * 1.001 + i * 0.1, 2), 1.5 + i) for i in range(5)]

        book_bids = bids if bids is not None else default_bids
        book_asks = asks if asks is not None else default_asks

        return OrderBookSnapshot(
            symbol=symbol,
            bids=book_bids,
            asks=book_asks,
            timestamp=ts,
        )
