"""Thread-safe Order Book Snapshot Cache (Sprint 9B)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

from paper_trading.models.market_models import OrderBookSnapshot

logger = logging.getLogger(__name__)


class OrderBookCache:
    """Thread-safe container maintaining latest read-only order book depth snapshots per symbol."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshots: Dict[str, OrderBookSnapshot] = {}

    def update_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """Update or set the latest OrderBookSnapshot for symbol."""
        if not snapshot or not snapshot.symbol:
            raise ValueError("Snapshot must be valid and contain a symbol.")

        with self._lock:
            self._snapshots[snapshot.symbol] = snapshot

    def get_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Get the latest read-only OrderBookSnapshot for symbol."""
        with self._lock:
            return self._snapshots.get(symbol)

    def get_all_snapshots(self) -> Dict[str, OrderBookSnapshot]:
        """Get copy of all current order book snapshots."""
        with self._lock:
            return dict(self._snapshots)

    def clear(self) -> None:
        """Clear all stored order book snapshots."""
        with self._lock:
            self._snapshots.clear()
