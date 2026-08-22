"""Leverage Engine calculating margin limits and buying power ratios.
"""

from __future__ import annotations

from typing import Dict

from research_platform.risk_management.models import LeverageReport


class LeverageEngine:
    """Evaluates initial margins, maintenance thresholds, and effective leverage limits."""

    def __init__(self, max_leverage: float = 2.0) -> None:
        self.max_leverage = max_leverage

    def evaluate_leverage(
        self,
        weights: Dict[str, float],
        equity: float = 100000.0
    ) -> LeverageReport:
        """Calculate total margins and remaining buying power."""
        gross = sum(abs(w) for w in weights.values())
        effective = gross  # e.g., effective leverage ratio is gross exposure ratio
        margin_used = gross * equity * 0.1  # 10% margin requirement
        buying_power = max(equity * self.max_leverage - gross * equity, 0.0)

        return LeverageReport(
            effective_leverage=effective,
            margin_used=margin_used,
            buying_power=buying_power
        )
