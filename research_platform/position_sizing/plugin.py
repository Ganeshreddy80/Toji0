"""Position Sizing and Capital Allocation DI Plugin.
"""

from __future__ import annotations

import logging

from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
from research_platform.position_sizing.events import PositionSizingInitialized

logger = logging.getLogger(__name__)


class PositionSizingPlugin:
    """Boot plugin for position sizing and capital allocation."""

    def __init__(self, container) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        event_bus = self.container.resolve("IEventBus")

        orchestrator = PositionSizingOrchestrator(
            event_bus=event_bus,
            container=self.container
        )
        self._orchestrator = orchestrator

        # Subscribe to ticks to feed cache
        event_bus.subscribe("system.position_valuation_updated", orchestrator.on_tick)
        event_bus.subscribe("system.market_data_received",        orchestrator.on_tick)

        logger.info(
            "PositionSizingPlugin: initialized — price cache subscribed."
        )

        # Register in DI container
        self.container.register("PositionSizingOrchestrator", instance=orchestrator)
        self.container.register(PositionSizingOrchestrator, instance=orchestrator)

        # Publish initialized event
        event_bus.publish(PositionSizingInitialized())

    def shutdown(self) -> None:
        logger.info("PositionSizingPlugin: shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
