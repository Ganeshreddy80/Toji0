"""AI Signal plugin DI registrations."""

from __future__ import annotations

import logging
from typing import Any
from research_platform.ai_signal.signal_generator import AISignalGenerator

logger = logging.getLogger(__name__)


class AISignalPlugin:
    """Hooks the AI Signal engine into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing AI Signal Engine Plugin...")
        try:
            generator = AISignalGenerator(container=self.container)
            self.container.register("AISignalGenerator", instance=generator)
            self.container.register(AISignalGenerator, instance=generator)
            logger.info("AI Signal Engine Plugin initialized successfully.")
        except Exception as e:
            logger.error("AI Signal Engine Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("AI Signal Engine Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
