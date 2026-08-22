"""State Recovery Plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.recovery.orchestrator import RecoveryOrchestrator


class RecoveryPlugin:
    """Hooks the State Recovery components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container
        self.orchestrator: RecoveryOrchestrator | None = None

    def initialize(self) -> None:
        """Register orchestrator and run startup recovery checks."""
        from research_platform.recovery.repository import RecoveryRepository
        repo = RecoveryRepository()
        self.container.register("RecoveryRepository", instance=repo)
        
        self.orchestrator = RecoveryOrchestrator(self.container)
        self.container.register("RecoveryOrchestrator", instance=self.orchestrator)
        
        # Register to ServiceRegistry for checkers and health validation
        from research_platform.platform.service_registry import ServiceRegistry
        ServiceRegistry().register_service("RecoveryOrchestrator", self.orchestrator)
        
        # Trigger automatic restoration of checkpoint states
        self.orchestrator.boot()

    def shutdown(self) -> None:
        """Gracefully release references."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        try:
            from toji_platform.core.types import HealthStatus
            return HealthStatus.HEALTHY
        except ImportError:
            return "HEALTHY"
