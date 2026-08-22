"""Confluence plugin DI registrations."""

from __future__ import annotations

import logging
from typing import Any
from research_platform.confluence.scoring_engine import ConfluenceScoringEngine

logger = logging.getLogger(__name__)


class ConfluencePlugin:
    """Hooks the confluence scoring engine into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Confluence Engine Plugin...")
        try:
            engine = ConfluenceScoringEngine(container=self.container)
            self.container.register("ConfluenceScoringEngine", instance=engine)
            self.container.register(ConfluenceScoringEngine, instance=engine)
            logger.info("Confluence Engine Plugin initialized successfully.")
        except Exception as e:
            logger.error("Confluence Engine Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("Confluence Engine Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
