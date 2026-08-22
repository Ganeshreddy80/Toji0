"""R55 Metrics & Observability Framework Plugin — platform DI integration."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MetricsPlugin:
    """Registers R55 MetricsOrchestrator and registry in the DI container, and manages collection loop lifecycle."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        logger.info("Initializing Metrics & Observability Subsystem (R55)...")
        try:
            from research_platform.metrics.orchestrator import MetricsOrchestrator
            from research_platform.metrics.registry import MetricsRegistry

            registry = MetricsRegistry()
            orchestrator = MetricsOrchestrator(registry=registry)

            self.container.register("MetricsOrchestrator", instance=orchestrator)
            self.container.register("MetricsRegistry", instance=registry)
            self.container.register(MetricsOrchestrator, instance=orchestrator)
            self.container.register(MetricsRegistry, instance=registry)

            self._orchestrator = orchestrator
            self._orchestrator.start()
            logger.info("R55 MetricsPlugin initialized and collection loop started.")
        except Exception as e:
            logger.error("R55 MetricsPlugin initialization failed: %s", e)

    def shutdown(self) -> None:
        try:
            if self._orchestrator:
                self._orchestrator.stop()
        except Exception as e:
            logger.warning("R55 MetricsPlugin shutdown error: %s", e)
        logger.info("R55 MetricsPlugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
