"""Validation Core Plugin registration.
"""

from __future__ import annotations

from research_platform.validation_core.interfaces import IValidationRepository
from research_platform.validation_core.orchestrator import ValidationCoreOrchestrator
from research_platform.validation_core.repository import ValidationRepository


class ValidationCorePlugin:
    """Hooks the validation core components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register validation repository and orchestrator mappings."""
        repo = ValidationRepository()
        self.container.register(IValidationRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = ValidationCoreOrchestrator(event_bus)
        self.container.register(ValidationCoreOrchestrator, instance=orchestrator)
