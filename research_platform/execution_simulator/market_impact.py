"""Market impact engine calculating impact costs based on order size.
"""

from __future__ import annotations


class MarketImpactEngine:
    """Calculates price shifts based on order size relative to L2 volume."""

    def calculate_impact(self, quantity: float, total_volume: float) -> float:
        if total_volume <= 0.0:
            return 0.0
        # Basic square root impact model
        fraction = quantity / total_volume
        return 0.15 * (fraction ** 0.5)
