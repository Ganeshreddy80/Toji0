"""OMS plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.oms.oms_core import OmsCore


class OmsPlugin:
    """Hooks the OMS components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = OmsCore(event_bus, container=self.container)
        self.container.register(OmsCore, instance=orchestrator)
        self.container.register("OmsCore", instance=orchestrator)

        from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
        self.container.register(OrderManagementSystemOrchestrator, instance=orchestrator)
        self.container.register("OrderManagementSystemOrchestrator", instance=orchestrator)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
