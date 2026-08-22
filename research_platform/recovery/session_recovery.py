"""Session recovery manager restoring paper trading sandbox parameters.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SessionRecoveryManager:
    """Restores active paper trading accounts, order states, and open logs."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_session(self, context_data: Dict[str, Any]) -> None:
        """Apply target session states to the active paper trading orchestrator."""
        logger.info("Restoring paper trading session state data...")
        try:
            paper_orch = self.container.resolve("PaperTradingOrchestrator")
            if paper_orch and hasattr(paper_orch, "restore_from_state"):
                paper_orch.restore_from_state(context_data)
        except Exception as e:
            logger.warning("Paper trading session state restore failed or was bypassed: %s", e)
