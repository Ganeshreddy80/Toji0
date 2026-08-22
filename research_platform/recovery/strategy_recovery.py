"""Strategy recovery manager.
"""

from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class StrategyRecoveryManager:
    """Restores active strategy lifecycle parameters and candidates configs."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_strategies(self, strategies_data: List[Any]) -> None:
        """Apply target strategy configurations to the active orchestrator."""
        logger.info("Restoring active strategies state...")
        try:
            strat_orch = self.container.resolve("StrategyLifecycleOrchestrator")
            if strat_orch and hasattr(strat_orch, "restore_strategies"):
                strat_orch.restore_strategies(strategies_data)
        except Exception as e:
            logger.warning("Strategy lifecycle state restore failed or was bypassed: %s", e)
