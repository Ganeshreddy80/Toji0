"""Portfolio Engine plugin registration.
"""

from __future__ import annotations

from research_platform.portfolio_engine.orchestrator import PortfolioEngineOrchestrator
from research_platform.portfolio_engine.repository import PortfolioRepository


class PortfolioEnginePlugin:
    """Hooks the portfolio engine components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = PortfolioRepository()
        self.container.register(PortfolioRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = PortfolioEngineOrchestrator(event_bus)
        self.container.register(PortfolioEngineOrchestrator, instance=orchestrator)
