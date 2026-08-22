"""Kelly allocation engine calculating fractional capital sizing weights.
"""

from __future__ import annotations

from typing import Dict, List


class KellyEngine:
    """Calculates fractions based on win rates and risk/reward parameters."""

    def calculate_kelly_fraction(
        self,
        assets: List[str],
        win_rates: Dict[str, float],
        win_loss_ratios: Dict[str, float]
    ) -> Dict[str, float]:
        weights = {}
        for a in assets:
            p = win_rates.get(a, 0.50)
            b = win_loss_ratios.get(a, 1.0)
            
            # Kelly formula: f = p - (1-p)/b
            fraction = p - (1.0 - p) / max(0.01, b)
            weights[a] = max(0.0, fraction)  # Clip negative weights

        return weights
