"""Audit engine generating state transition audit cards.
"""

from __future__ import annotations

from research_platform.strategy_lifecycle.interfaces import IAuditEngine
from research_platform.strategy_lifecycle.models import StrategyAudit


class AuditEngine(IAuditEngine):
    """Tracks chronological change histories logs for strategy status transitions."""

    def log_action(self, action: str, strategy_id: str, prev_state: str, new_state: str, actor: str, reason: str) -> StrategyAudit:
        return StrategyAudit(
            action=action,
            strategy_id=strategy_id,
            previous_state=prev_state,
            new_state=new_state,
            actor=actor,
            reason=reason
        )
