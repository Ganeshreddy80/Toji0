"""Research Data Platform plugin registration.
"""

from __future__ import annotations

from research_platform.data_platform.orchestrator import ResearchDataPlatformOrchestrator
from research_platform.data_platform.repository import DataPlatformRepository


class ResearchDataPlatformPlugin:
    """Hooks the research data platform components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = DataPlatformRepository()
        self.container.register(DataPlatformRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = ResearchDataPlatformOrchestrator(event_bus)
        self.container.register(ResearchDataPlatformOrchestrator, instance=orchestrator)
