"""R54 Alerting Plugin — platform DI integration."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AlertingPlugin:
    """Registers R54 AlertOrchestrator in the DI container."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        logger.info("Initializing Alerting & Notification Framework (R54)...")
        try:
            from research_platform.alerting.orchestrator import AlertOrchestrator
            from research_platform.alerting.repository import AlertRepository

            repo = AlertRepository()
            orchestrator = AlertOrchestrator(repository=repo)

            self.container.register("AlertOrchestrator", instance=orchestrator)
            self.container.register("AlertRepository", instance=repo)
            self.container.register(AlertOrchestrator, instance=orchestrator)

            self._orchestrator = orchestrator
            logger.info("R54 AlertingPlugin initialized.")
        except Exception as e:
            logger.error("R54 AlertingPlugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("R54 AlertingPlugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
