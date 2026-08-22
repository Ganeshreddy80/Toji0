"""Slippage engine calculating slippage offsets.
"""

from __future__ import annotations


class SlippageEngine:
    """Calculates slippage offsets based on execution volumes."""

    def calculate_slippage(self, quantity: float, volatility: float = 0.20) -> float:
        # Volatility scaled slippage calculation
        return 0.0005 * quantity * volatility
