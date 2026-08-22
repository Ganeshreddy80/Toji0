"""TWAP engine simulating time weighted split orders.
"""

from __future__ import annotations

from typing import List, Tuple


class TwapEngine:
    """Calculates simple averages of prices over time ticks."""

    def calculate_twap(self, fills: List[Tuple[float, float]]) -> float:
        if not fills:
            return 0.0
        # Simple arithmetic average
        return sum(price for price, _ in fills) / len(fills)
