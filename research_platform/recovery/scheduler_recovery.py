"""Scheduler recovery manager.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SchedulerRecoveryManager:
    """Restores scheduler cron targets and queued execution jobs."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_scheduler(self, scheduler_data: Dict[str, Any]) -> None:
        """Apply target scheduler configurations to the active orchestrator."""
        logger.info("Restoring scheduler cron targets and crontabs...")
        try:
            sched = self.container.resolve("StrategySchedulerOrchestrator")
            if sched and hasattr(sched, "restore_from_state"):
                sched.restore_from_state(scheduler_data)
        except Exception as e:
            logger.warning("Strategy scheduler state restore failed or was bypassed: %s", e)
