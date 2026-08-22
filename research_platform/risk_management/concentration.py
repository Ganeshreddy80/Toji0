"""Concentration Risk calculator checking sector limits and portfolio imbalance.
"""

from __future__ import annotations

from typing import Dict

from research_platform.risk_management.models import ConcentrationReport


class ConcentrationRiskEngine:
    """Detects single asset clusters and flags portfolio imbalances."""

    def __init__(self, limit: float = 0.40) -> None:
        self.limit = limit

    def check_concentration(self, weights: Dict[str, float]) -> ConcentrationReport:
        """Find max weight allocation and score imbalance ratios."""
        if not weights:
            return ConcentrationReport(max_concentration=0.0, imbalance_score=0.0)

        max_w = max(abs(w) for w in weights.values())
        return ConcentrationReport(
            max_concentration=max_w,
            imbalance_score=1.0 if max_w > self.limit else 0.0
        )
