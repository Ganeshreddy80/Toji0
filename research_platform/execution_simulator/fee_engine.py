"""Fee engine calculating commissions fees.
"""

from __future__ import annotations


class FeeEngine:
    """Calculates exchange fee commissions."""

    def calculate_fees(self, value: float) -> float:
        # Default exchange commission fee 5 bps (0.05%)
        return value * 0.0005
