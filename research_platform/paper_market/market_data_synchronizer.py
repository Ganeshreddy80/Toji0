"""Synchronizer feeding pricing ticks to Paper Trading and downstream subsystems.
"""

from __future__ import annotations

import logging
from typing import Any
from research_platform.paper_market.interfaces import IMarketDataSynchronizer

logger = logging.getLogger(__name__)


class MarketDataSynchronizer(IMarketDataSynchronizer):
    """Synchronizes pricing updates and updates portfolio valuations."""

    def __init__(self, container: Any) -> None:
        self._container = container

    def synchronize(self, symbol: str, price: float) -> None:
        """Propagate price ticks to recalculate unrealized PnL, equity, and drawdowns."""
        p_key = "research_platform.paper_trading.orchestrator.PaperTradingOrchestrator"
        if self._container.has(p_key):
            paper_orch = self._container.resolve(p_key)
            # Update market price and trigger calculations
            paper_orch.update_market_price(symbol, price)
            logger.debug("Synchronized price update for %s: %.4f", symbol, price)
        else:
            logger.warning("MarketDataSynchronizer: PaperTradingOrchestrator not registered in DI container.")
