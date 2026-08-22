"""Kelly Criterion position sizing optimization rules."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KellySizingEngine:
    """Calculates optimal leverage fractions using win-rate and risk-reward ratios."""

    def __init__(self, fraction_multiplier: float = 0.25, max_fraction: float = 0.10) -> None:
        self.fraction_multiplier = fraction_multiplier
        self.max_fraction = max_fraction

    def calculate_sizing(self, win_rate: float, risk_reward: float) -> float:
        """Computes conservative fractional Kelly allocation percentage of account equity.

        Kelly % = WinRate - ((1 - WinRate) / RiskReward)
        """
        if win_rate <= 0.0 or win_rate >= 1.0 or risk_reward <= 0.0:
            return 0.0

        # Calculate raw Kelly fraction
        raw_kelly = win_rate - ((1.0 - win_rate) / risk_reward)
        
        if raw_kelly <= 0.0:
            return 0.0

        # Apply fraction multiplier (fractional Kelly) and enforce maximum limit
        scaled_kelly = raw_kelly * self.fraction_multiplier
        final_sizing = min(scaled_kelly, self.max_fraction)

        return float(final_sizing)
