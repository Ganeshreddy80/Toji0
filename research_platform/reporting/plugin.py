"""Reporting plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.reporting.orchestrator import ReportingOrchestrator


class ReportingPlugin:
    """Hooks the reporting components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        from research_platform.reporting.reporter import PerformanceReporter
        orchestrator = ReportingOrchestrator(event_bus, container=self.container)
        reporter = PerformanceReporter(container=self.container)
        self.container.register(ReportingOrchestrator, instance=orchestrator)
        self.container.register(PerformanceReporter, instance=reporter)
        self.container.register("PerformanceReporter", instance=reporter)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
