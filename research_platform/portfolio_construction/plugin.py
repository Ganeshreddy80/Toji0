"""Portfolio Construction plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.portfolio_construction.orchestrator import PortfolioConstructionOrchestrator


class PortfolioConstructionPlugin:
    """Hooks the portfolio construction components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings and start construction listening."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = PortfolioConstructionOrchestrator(event_bus, container=self.container)
        self.container.register(PortfolioConstructionOrchestrator, instance=orchestrator)
        orchestrator.start_construction()
        self._orchestrator = orchestrator

    def shutdown(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "_orchestrator") and self._orchestrator:
            self._orchestrator.stop_construction()

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
