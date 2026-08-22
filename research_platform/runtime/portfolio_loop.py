"""Portfolio Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class PortfolioLoop(IRuntimeLoop):
    """Calculates allocation weights and rebalancing targets."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing PortfolioLoop adjustments...")
        try:
            port_engine = self.container.resolve("PortfolioEngineOrchestrator")
            if port_engine and hasattr(port_engine, "calculate_allocations"):
                context["allocations"] = port_engine.calculate_allocations()
        except Exception:
            pass

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("PortfolioLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
