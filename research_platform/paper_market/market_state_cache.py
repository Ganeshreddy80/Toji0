"""Thread-safe cache storing latest symbol prices from the live ticks stream.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional


class MarketStateCache:
    """Thread-safe storage caching standard price fields for active symbols."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prices: Dict[str, float] = {}
        self._timestamps: Dict[str, float] = {}

    def set_price(self, symbol: str, price: float) -> None:
        import time
        with self._lock:
            self._prices[symbol] = price
            self._timestamps[symbol] = time.perf_counter()

    def get_price(self, symbol: str) -> Optional[float]:
        with self._lock:
            return self._prices.get(symbol)

    def get_last_update_time(self, symbol: str) -> Optional[float]:
        with self._lock:
            return self._timestamps.get(symbol)

    def list_symbols(self) -> List[str]:
        with self._lock:
            return list(self._prices.keys())
