"""Multi Timeframe plugin registration."""

from __future__ import annotations

import logging
from typing import Any
from research_platform.multi_timeframe.top_down_analysis import TopDownAnalysisEngine

logger = logging.getLogger(__name__)


class MultiTimeframePlugin:
    """Hooks the top-down analysis engine into the DI container during boot."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Multi Timeframe Plugin...")
        try:
            engine = TopDownAnalysisEngine(container=self.container)
            self.container.register("TopDownAnalysisEngine", instance=engine)
            self.container.register(TopDownAnalysisEngine, instance=engine)
            logger.info("Multi Timeframe Plugin initialized successfully.")
        except Exception as e:
            logger.error("Multi Timeframe Plugin initialization failed: %s", e)

    def shutdown(self) -> None:
        logger.info("Multi Timeframe Plugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
