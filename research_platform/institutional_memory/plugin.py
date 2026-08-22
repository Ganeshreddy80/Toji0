"""Institutional Memory plugin registration.
"""

from __future__ import annotations

from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.institutional_memory.repository import InstitutionalMemoryRepository


class InstitutionalMemoryPlugin:
    """Hooks the institutional memory platform components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = InstitutionalMemoryRepository()
        self.container.register(InstitutionalMemoryRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = InstitutionalMemoryOrchestrator(event_bus)
        self.container.register(InstitutionalMemoryOrchestrator, instance=orchestrator)
