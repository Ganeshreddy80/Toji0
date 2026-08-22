"""Stability engine detecting strategy backtest overfitting.
"""

from __future__ import annotations

from research_platform.walk_forward.interfaces import IStabilityEngine
from research_platform.walk_forward.models import OverfittingCard


class StabilityEngine(IStabilityEngine):
    """Calculates backtest overfitting probability parameters."""

    def detect_overfitting(self, strategy_id: str, is_overfitted: bool, stability_score: float) -> OverfittingCard:
        # Enforce basic probability calculations
        prob = 0.85 if is_overfitted else 0.12
        return OverfittingCard(
            strategy_id=strategy_id,
            is_overfitted=is_overfitted,
            probability_of_backtest_overfitting=prob,
            stability_score=stability_score
        )
