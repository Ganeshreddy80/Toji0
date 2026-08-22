"""Recovery engine generating estimated steps to restore distressed states.
"""

from __future__ import annotations

from typing import List
from research_platform.stress_testing.models import RecoveryPlan


class RecoveryEngine:
    """Recommends deleveraging and rebalancing recovery steps."""

    def compile_recovery_plan(self, run_id: str, drawdown_pct: float) -> RecoveryPlan:
        steps = []
        if drawdown_pct > 0.20:
            steps = ["Deleverage immediately to 0.5x", "Hedge beta exposure via index shorts", "Rebalance weekly"]
            days = 90
        elif drawdown_pct > 0.05:
            steps = ["Reduce size on high-beta names", "Rebalance daily"]
            days = 30
        else:
            steps = ["No immediate action needed"]
            days = 5

        return RecoveryPlan(
            run_id=run_id,
            recovery_steps=steps,
            estimated_days=days
        )
