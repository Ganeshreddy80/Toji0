"""Liquidity Risk calculator estimating slippages and spreads.
"""

from __future__ import annotations

from research_platform.risk_management.models import LiquidityReport


class LiquidityRiskEngine:
    """Estimates execution difficulty based on average volumes."""

    def estimate_liquidity(self, quantity: float, avg_volume: float = 10000.0) -> LiquidityReport:
        """Estimate execution slippage percentage."""
        # Simple slippage estimation model: slippage increases with size ratio
        ratio = quantity / avg_volume if avg_volume > 0.0 else 0.0
        slippage = ratio * 0.01  # e.g., 1% slippage for 100% volume

        return LiquidityReport(
            avg_volume=avg_volume,
            estimated_slippage=slippage,
            liquidity_score=max(1.0 - ratio, 0.0)
        )
