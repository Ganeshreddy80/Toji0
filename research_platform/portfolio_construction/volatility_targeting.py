"""Volatility targeting engine scaling weights to match risk targets.
"""

from __future__ import annotations

from typing import Dict


class VolatilityTargetingEngine:
    """Scales weights to control leverage and remain within volatility boundaries."""

    def scale_to_target(
        self,
        weights: Dict[str, float],
        realized_volatility: float,
        target_volatility: float = 0.15
    ) -> Dict[str, float]:
        if realized_volatility <= 0.0:
            return dict(weights)

        # Scale factor calculation
        scale = target_volatility / realized_volatility
        # Limit scale factor to a max leverage of 2.0
        leverage_limit = min(2.0, scale)

        return {asset: w * leverage_limit for asset, w in weights.items()}
