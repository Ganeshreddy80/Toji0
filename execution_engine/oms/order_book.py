"""In-memory Order Book Tracker for market depth analysis.

Provides simulated order book snapshots used by EMS algorithms
(VWAP, POV) to estimate market impact and optimal slice sizing.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from execution_engine.core.models import OrderBookLevel, OrderBookSnapshot

logger = logging.getLogger(__name__)


class OrderBookTracker:
    """Thread-safe in-memory order book tracker.

    Maintains the latest order book snapshot per symbol for use
    by execution algorithms that need market depth information.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._books: Dict[str, OrderBookSnapshot] = {}

    def update_book(self, snapshot: OrderBookSnapshot) -> None:
        """Update the order book snapshot for a symbol."""
        with self._lock:
            self._books[snapshot.symbol.upper()] = snapshot
            logger.debug(
                "OrderBookTracker: Updated book for %s (%d bids, %d asks).",
                snapshot.symbol, len(snapshot.bids), len(snapshot.asks),
            )

    def get_book(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Retrieve the latest order book snapshot for a symbol."""
        with self._lock:
            return self._books.get(symbol.upper())

    def get_mid_price(self, symbol: str) -> Optional[float]:
        """Calculate the mid price from the current order book."""
        book = self.get_book(symbol)
        if not book:
            return None
        if book.mid_price is not None:
            return book.mid_price
        if book.bids and book.asks:
            return (book.bids[0].price + book.asks[0].price) / 2.0
        return None

    def get_spread(self, symbol: str) -> Optional[float]:
        """Calculate the bid-ask spread from the current order book."""
        book = self.get_book(symbol)
        if not book:
            return None
        if book.spread is not None:
            return book.spread
        if book.bids and book.asks:
            return book.asks[0].price - book.bids[0].price
        return None

    def get_available_liquidity(self, symbol: str, side: str, depth: int = 5) -> float:
        """Calculate total available liquidity on one side of the book up to N levels.

        Args:
            symbol: Ticker symbol.
            side: 'bid' or 'ask'.
            depth: Number of price levels to aggregate.
        """
        book = self.get_book(symbol)
        if not book:
            return 0.0
        levels = book.bids if side.lower() == "bid" else book.asks
        return sum(level.quantity for level in levels[:depth])

    def estimate_market_impact(self, symbol: str, side: str, quantity: float) -> float:
        """Estimate price impact of executing a given quantity against the book.

        Walks the order book levels and calculates the volume-weighted average
        price difference from the best price (market impact).

        Args:
            symbol: Ticker symbol.
            side: 'buy' (walks asks) or 'sell' (walks bids).
            quantity: Order quantity to simulate.

        Returns:
            Estimated price impact as a fraction of the best price.
        """
        book = self.get_book(symbol)
        if not book:
            return 0.0

        levels = book.asks if side.lower() == "buy" else book.bids
        if not levels:
            return 0.0

        best_price = levels[0].price
        remaining = quantity
        total_cost = 0.0

        for level in levels:
            fill_qty = min(remaining, level.quantity)
            total_cost += fill_qty * level.price
            remaining -= fill_qty
            if remaining <= 0:
                break

        if quantity <= 0:
            return 0.0

        vwap = total_cost / (quantity - remaining) if (quantity - remaining) > 0 else best_price
        impact = abs(vwap - best_price) / best_price if best_price > 0 else 0.0
        return impact

    def generate_simulated_book(
        self,
        symbol: str,
        mid_price: float,
        spread_pct: float = 0.001,
        levels: int = 10,
        base_quantity: float = 100.0,
    ) -> OrderBookSnapshot:
        """Generate a simulated order book for paper trading.

        Creates synthetic bids and asks around a mid price with
        increasing quantity at wider price levels (depth-of-book effect).
        """
        half_spread = mid_price * spread_pct / 2.0

        bids = []
        asks = []
        for i in range(levels):
            offset = half_spread * (1 + i * 0.5)
            qty_multiplier = 1.0 + i * 0.3

            bids.append(OrderBookLevel(
                price=round(mid_price - offset, 8),
                quantity=round(base_quantity * qty_multiplier, 4),
            ))
            asks.append(OrderBookLevel(
                price=round(mid_price + offset, 8),
                quantity=round(base_quantity * qty_multiplier, 4),
            ))

        snapshot = OrderBookSnapshot(
            symbol=symbol.upper(),
            bids=bids,
            asks=asks,
            mid_price=mid_price,
            spread=round(2 * half_spread, 8),
        )
        self.update_book(snapshot)
        return snapshot

    def clear(self) -> None:
        """Clear all tracked order books."""
        with self._lock:
            self._books.clear()
