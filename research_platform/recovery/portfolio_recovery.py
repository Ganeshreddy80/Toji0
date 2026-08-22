"""Portfolio recovery manager.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PortfolioRecoveryManager:
    """Restores active portfolio weights and optimization properties."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def restore_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Apply target portfolio configurations to the portfolio engine."""
        logger.info("Restoring portfolio construction allocations...")
        try:
            port_orch = self.container.resolve("PortfolioEngineOrchestrator")
            if port_orch and hasattr(port_orch, "restore_from_state"):
                port_orch.restore_from_state(portfolio_data)
        except Exception as e:
            logger.warning("Portfolio engine state restore failed or was bypassed: %s", e)
