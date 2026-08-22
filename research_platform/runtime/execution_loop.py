"""Execution Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class ExecutionLoop(IRuntimeLoop):
    """Processes OMS order entries and virtual paper trades executions."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing ExecutionLoop broker cycles...")
        signals = context.get("validated_signals", [])
        
        # 1. Routing to OMS Orchestrator
        try:
            oms = self.container.resolve("OMSOrchestrator")
            if oms and hasattr(oms, "route_order"):
                for sig in signals:
                    oms.route_order(sig)
        except Exception:
            pass

        # 2. Virtual execution via PaperTradingOrchestrator
        try:
            paper_trading = self.container.resolve("PaperTradingOrchestrator")
            if paper_trading and hasattr(paper_trading, "execute_pending_orders"):
                paper_trading.execute_pending_orders()
        except Exception:
            pass

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("ExecutionLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
