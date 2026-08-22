"""Paper market plugin registration.
"""

from __future__ import annotations

import logging
from typing import Any
from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.paper_market.paper_execution_router import PaperExecutionRouter

logger = logging.getLogger(__name__)


class PaperMarketPlugin:
    """Hooks the paper market components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = PaperMarketOrchestrator(event_bus, container=self.container)
        self.container.register(PaperMarketOrchestrator, instance=orchestrator)

        # Also register PaperMarketOrchestrator by full module path for resolution flexibility
        _full_key = "research_platform.paper_market.orchestrator.PaperMarketOrchestrator"
        if not self.container.has(_full_key):
            self.container.register(_full_key, instance=orchestrator)

        # Register PaperExecutionRouter directly so OmsCore can resolve it without going through PaperMarketOrchestrator
        exec_router = orchestrator.execution_router
        if not self.container.has(PaperExecutionRouter):
            self.container.register(PaperExecutionRouter, instance=exec_router)
        if not self.container.has("PaperExecutionRouter"):
            self.container.register("PaperExecutionRouter", instance=exec_router)
        logger.info("PaperMarketPlugin: PaperExecutionRouter available in DI container (mode=%s).", exec_router.mode)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
