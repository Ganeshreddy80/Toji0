"""Monitoring Center plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.monitoring.orchestrator import MonitoringOrchestrator


class MonitoringPlugin:
    """Hooks the monitoring center components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        from research_platform.monitoring.ops_center import OperationsCenter
        orchestrator = MonitoringOrchestrator(event_bus, container=self.container)
        ops_center = OperationsCenter(container=self.container)
        self.container.register(MonitoringOrchestrator, instance=orchestrator)
        self.container.register(OperationsCenter, instance=ops_center)
        self.container.register("OperationsCenter", instance=ops_center)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
