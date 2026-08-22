"""Risk Management plugin registration.
"""

from __future__ import annotations

from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
from research_platform.risk_management.repository import RiskRepository


class RiskManagementPlugin:
    """Hooks the risk management components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = RiskRepository()
        self.container.register(RiskRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = RiskManagementOrchestrator(event_bus)
        self.container.register(RiskManagementOrchestrator, instance=orchestrator)
