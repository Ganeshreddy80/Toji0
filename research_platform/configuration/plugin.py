"""Configuration plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.configuration.orchestrator import ConfigurationOrchestrator


class ConfigurationPlugin:
    """Hooks the configuration components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = ConfigurationOrchestrator(event_bus, container=self.container)
        self.container.register(ConfigurationOrchestrator, instance=orchestrator)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
