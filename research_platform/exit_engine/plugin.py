"""Exit Engine DI Plugin.
"""

from __future__ import annotations

import logging

from research_platform.exit_engine.orchestrator import ExitEngineOrchestrator

logger = logging.getLogger(__name__)


class ExitEnginePlugin:
    """Boot plugin for the Exit Engine subsystem."""

    def __init__(self, container) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        event_bus = self.container.resolve("IEventBus")

        orchestrator = ExitEngineOrchestrator(
            event_bus=event_bus,
            container=self.container
        )
        self._orchestrator = orchestrator

        # Subscribe to topics
        event_bus.subscribe("system.position_valuation_updated", orchestrator.on_valuation_update)
        event_bus.subscribe("system.trade_closed",               orchestrator.on_trade_closed)
        event_bus.subscribe("system.order_rejected",             orchestrator.on_order_rejected)
        event_bus.subscribe("system.o_m_s_order_state_changed",   orchestrator.on_order_state_changed)

        logger.info(
            "ExitEnginePlugin: initialized — subscribed to position_valuation, trade_closed, order_rejected, state_changed."
        )

        # Register in the DI container
        self.container.register("ExitEngine", instance=orchestrator)
        self.container.register("ExitEngineOrchestrator", instance=orchestrator)
        self.container.register(ExitEngineOrchestrator, instance=orchestrator)

    def shutdown(self) -> None:
        logger.info("ExitEnginePlugin: shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
