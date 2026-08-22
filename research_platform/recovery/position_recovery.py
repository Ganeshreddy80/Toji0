"""Position recovery manager.
"""

from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class PositionRecoveryManager:
    """Restores active open positions from checkpoint states."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_positions(self, positions_data: List[Any]) -> None:
        """Apply target position balances to the active OMS/paper broker."""
        logger.info("Restoring active open position balances...")
        try:
            oms = self.container.resolve("OMSOrchestrator")
            if oms and hasattr(oms, "restore_positions"):
                oms.restore_positions(positions_data)
        except Exception as e:
            logger.warning("OMS position state restore failed or was bypassed: %s", e)
