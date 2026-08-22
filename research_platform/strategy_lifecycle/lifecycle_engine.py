"""Lifecycle engine validating allowed state transitions.
"""

from __future__ import annotations

from research_platform.strategy_lifecycle.interfaces import ILifecycleEngine
from research_platform.strategy_lifecycle.models import StrategyStatus


class LifecycleEngine(ILifecycleEngine):
    """Enforces migration pathways across backtest, paper, and production stages."""

    def __init__(self) -> None:
        # Define valid transitions dictionary
        self._allowed_map = {
            "DRAFT": ["RESEARCH", "RETIRED"],
            "RESEARCH": ["BACKTEST", "DRAFT", "RETIRED"],
            "BACKTEST": ["OPTIMIZATION", "RESEARCH", "RETIRED"],
            "OPTIMIZATION": ["WALKFORWARD", "BACKTEST", "RETIRED"],
            "WALKFORWARD": ["PAPER", "OPTIMIZATION", "RETIRED"],
            "PAPER": ["CANDIDATE", "PAUSED", "RETIRED"],
            "CANDIDATE": ["APPROVED", "REJECTED", "RETIRED"],
            "APPROVED": ["PRODUCTION", "RETIRED"],
            "PRODUCTION": ["PAUSED", "RETIRED"],
            "PAUSED": ["PRODUCTION", "PAPER", "RETIRED"],
            "REJECTED": ["DRAFT", "RETIRED"],
            "RETIRED": []
        }

    def transition_state(self, strategy: StrategyStatus, target_state: str, actor: str, reason: str) -> StrategyStatus:
        current = strategy.status
        if target_state not in self._allowed_map.get(current, []):
            # Special command pause/retire overrides
            if target_state == "RETIRED" and current != "RETIRED":
                pass
            elif target_state == "PAUSED" and current in ["PRODUCTION", "PAPER"]:
                pass
            else:
                raise ValueError(f"Invalid Transition: Cannot transition strategy from '{current}' to '{target_state}'.")

        updated = strategy.model_copy(update={"status": target_state})
        return updated
