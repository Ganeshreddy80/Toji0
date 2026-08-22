"""Heartbeat monitor assessing feed freshness.
"""

from __future__ import annotations

import logging
import time
from research_platform.paper_market.market_state_cache import MarketStateCache

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Verifies symbol update ticks arrive within configured timeout bounds."""

    def __init__(self, cache: MarketStateCache) -> None:
        self._cache = cache

    def check_heartbeat(self, symbol: str, max_gap_seconds: float = 5.0) -> bool:
        """Return True if price updates arrived recently, False if feed is stale."""
        last_t = self._cache.get_last_update_time(symbol)
        if last_t is None:
            logger.warning("Heartbeat: Symbol '%s' has received no ticks.", symbol)
            return False

        gap = time.perf_counter() - last_t
        is_fresh = gap <= max_gap_seconds
        
        if not is_fresh:
            logger.error("Heartbeat Stale Breach: Symbol '%s' last updated %.2f sec ago (Limit: %.2f sec).",
                         symbol, gap, max_gap_seconds)
        
        return is_fresh
