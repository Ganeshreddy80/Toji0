"""Strategy Lab plugin registration.
"""

from __future__ import annotations

from research_platform.strategy_lab.orchestrator import StrategyLabOrchestrator
from research_platform.strategy_lab.repository import StrategyRepository


class StrategyLabPlugin:
    """Hooks the Strategy Lab components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register strategy repository and orchestrator mappings."""
        repo = StrategyRepository()
        self.container.register(StrategyRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = StrategyLabOrchestrator(event_bus)
        self.container.register(StrategyLabOrchestrator, instance=orchestrator)
