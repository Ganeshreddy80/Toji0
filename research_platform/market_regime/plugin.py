"""Market Regime plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.market_regime.orchestrator import MarketRegimeOrchestrator


class MarketRegimePlugin:
    """Hooks the market regime intelligence components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = MarketRegimeOrchestrator(event_bus, container=self.container)
        self.container.register(MarketRegimeOrchestrator, instance=orchestrator)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
