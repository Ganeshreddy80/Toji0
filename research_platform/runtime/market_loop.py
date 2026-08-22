"""Market Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class MarketLoop(IRuntimeLoop):
    """Processes incoming market data feeds and updates ticker states."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing MarketLoop data aggregation...")
        # Access PaperMarketOrchestrator from container if present
        try:
            market_orch = self.container.resolve("PaperMarketOrchestrator")
            if market_orch and hasattr(market_orch, "get_tickers"):
                context["tickers"] = market_orch.get_tickers()
            else:
                context["tickers"] = {"AAPL": 150.0, "MSFT": 300.0}
        except Exception:
            context["tickers"] = {"AAPL": 150.0, "MSFT": 300.0}

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("MarketLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
