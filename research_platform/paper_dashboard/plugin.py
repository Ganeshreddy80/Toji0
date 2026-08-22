"""Paper dashboard plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.paper_dashboard.orchestrator import PaperDashboardOrchestrator
from research_platform.paper_dashboard.console_controller import ConsoleController


class PaperDashboardPlugin:
    """Hooks the paper dashboard components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = PaperDashboardOrchestrator(event_bus, container=self.container)
        self.container.register(PaperDashboardOrchestrator, instance=orchestrator)

        controller = ConsoleController(orchestrator)
        self.container.register(ConsoleController, instance=controller)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
