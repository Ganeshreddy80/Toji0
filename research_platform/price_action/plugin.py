"""Price Action Plugin mapping registrations inside DI container."""

from __future__ import annotations

import logging
from typing import Any

from research_platform.price_action.repository import PriceActionRepository
from research_platform.price_action.orchestrator import PriceActionOrchestrator

logger = logging.getLogger(__name__)


class PriceActionPlugin:
    """Hooks the price action components into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        logger.info("Initializing Price Action Engine Plugin...")
        try:
            event_bus = self.container.resolve("IEventBus")
            repo = PriceActionRepository()
            orch = PriceActionOrchestrator(event_bus=event_bus, repository=repo, container=self.container)

            # Register bindings
            self.container.register("PriceActionRepository", instance=repo)
            self.container.register("PriceActionOrchestrator", instance=orch)
            self.container.register(PriceActionRepository, instance=repo)
            self.container.register(PriceActionOrchestrator, instance=orch)

            self._orchestrator = orch
            logger.info("Price Action Engine Plugin initialized successfully.")
        except Exception as e:
            logger.error("Price Action Engine Plugin failed to boot: %s", e)

    def shutdown(self) -> None:
        logger.info("Price Action Engine Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
