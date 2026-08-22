"""Volatility engine simulating volatility multiplier shocks.
"""

from __future__ import annotations


class VolatilityEngine:
    """Calculates shocked portfolio value based on volatility scaling factor."""

    def shock_portfolio(self, initial_value: float, vol_multiplier: float) -> float:
        # High vol multiplier reduces asset value proportionately
        shift = 0.05 * (vol_multiplier - 1.0)
        return max(0.0, initial_value * (1.0 - shift))
