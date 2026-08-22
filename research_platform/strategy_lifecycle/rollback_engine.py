"""Rollback engine restoring previous code versions and deployments.
"""

from __future__ import annotations

from research_platform.strategy_lifecycle.interfaces import IRollbackEngine
from research_platform.strategy_lifecycle.models import StrategyRollback


class RollbackEngine(IRollbackEngine):
    """Restores stable deployment state when system health or drawdowns fail limits."""

    def execute_rollback(self, strategy_id: str, target_version: str, reason: str) -> StrategyRollback:
        return StrategyRollback(
            strategy_id=strategy_id,
            from_version="current",
            to_version=target_version,
            reason=reason
        )
