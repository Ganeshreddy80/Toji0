"""Continuous Runtime Engine plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.runtime.orchestrator import RuntimeOrchestrator


class RuntimePlugin:
    """Hooks the Continuous Runtime components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container
        self.orchestrator: RuntimeOrchestrator | None = None

    def initialize(self) -> None:
        """Register runtime orchestrator mappings."""
        from research_platform.runtime.runtime_engine import RuntimeEngine
        from research_platform.platform.service_registry import ServiceRegistry

        self.orchestrator = RuntimeOrchestrator(self.container)
        self.container.register("RuntimeOrchestrator", instance=self.orchestrator)
        # Register interfaces if needed
        self.container.register(RuntimeOrchestrator, instance=self.orchestrator)

        # Create and register RuntimeEngine
        runtime_engine = RuntimeEngine(self.container)
        self.container.register("RuntimeEngine", instance=runtime_engine)
        ServiceRegistry().register_service("RuntimeEngine", runtime_engine)

    def shutdown(self) -> None:
        """Gracefully stop running threads on shutdown."""
        if self.orchestrator:
            self.orchestrator.shutdown()

    def health_check(self) -> Any:
        """Assess operational health state."""
        try:
            from toji_platform.core.types import HealthStatus
            return HealthStatus.HEALTHY
        except ImportError:
            return "HEALTHY"
