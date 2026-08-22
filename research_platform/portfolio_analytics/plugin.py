"""Portfolio analytics plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.portfolio_analytics.orchestrator import PortfolioAnalyticsOrchestrator


class PortfolioAnalyticsPlugin:
    """Hooks the portfolio analytics components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings and start analytics listening."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = PortfolioAnalyticsOrchestrator(event_bus, container=self.container)
        self.container.register(PortfolioAnalyticsOrchestrator, instance=orchestrator)
        orchestrator.start_analytics()
        self._orchestrator = orchestrator

    def shutdown(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "_orchestrator") and self._orchestrator:
            self._orchestrator.stop_analytics()

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
