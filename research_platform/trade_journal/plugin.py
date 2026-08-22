"""Trade journal plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator


class TradeJournalPlugin:
    """Hooks the trade journal components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = TradeJournalOrchestrator(event_bus, container=self.container)
        self.container.register(TradeJournalOrchestrator, instance=orchestrator)
        orchestrator.start_journaling()
        self._orchestrator = orchestrator

    def shutdown(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "_orchestrator") and self._orchestrator:
            self._orchestrator.stop_journaling()

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
