"""Observability plugin registration.
"""

from __future__ import annotations

from research_platform.observability.orchestrator import ObservabilityOrchestrator
from research_platform.observability.repository import ObservabilityRepository


class ObservabilityPlugin:
    """Hooks the observability platform components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = ObservabilityRepository()
        self.container.register(ObservabilityRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = ObservabilityOrchestrator(event_bus)
        self.container.register(ObservabilityOrchestrator, instance=orchestrator)
