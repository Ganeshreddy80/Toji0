"""VWAP engine simulating volume weighted split orders.
"""

from __future__ import annotations

from typing import List, Tuple


class VwapEngine:
    """Calculates weighted average prices from split execution outcomes."""

    def calculate_vwap(self, fills: List[Tuple[float, float]]) -> float:
        if not fills:
            return 0.0
        total_val = sum(price * qty for price, qty in fills)
        total_qty = sum(qty for _, qty in fills)
        if total_qty <= 0.0:
            return 0.0
        return total_val / total_qty
