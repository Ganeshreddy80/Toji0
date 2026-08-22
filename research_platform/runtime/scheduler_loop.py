"""Scheduler Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class SchedulerLoop(IRuntimeLoop):
    """Executes scheduled execution jobs and ticks timer parameters."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing SchedulerLoop cron intervals...")
        try:
            scheduler = self.container.resolve("StrategySchedulerOrchestrator")
            if scheduler and hasattr(scheduler, "tick"):
                scheduler.tick()
        except Exception:
            pass

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("SchedulerLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
