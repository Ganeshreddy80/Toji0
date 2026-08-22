"""Portfolio Brain Allocation Engine computing Kelly fractions and correlation risks.
"""

from __future__ import annotations
from typing import Dict, Any, List

class PortfolioAllocationEngine:
    """Manages position sizing and capital allocation across assets with correlation filters."""

    def __init__(self, max_risk_pct: float = 2.0) -> None:
        self.max_risk_pct = max_risk_pct  # e.g., never risk more than 2% of capital per trade

    def calculate_kelly_fraction(self, win_rate: float, win_loss_ratio: float) -> float:
        """Computes standard Kelly criterion: Kelly % = W - (1 - W) / R."""
        w = win_rate / 100.0 if win_rate > 1.0 else win_rate
        r = win_loss_ratio
        if r <= 0.0:
            return 0.0
        kelly = w - (1.0 - w) / r
        return max(0.0, min(kelly, 1.0))

    def calculate_allocations(
        self,
        assets: List[str],
        win_rates: Dict[str, float],
        win_loss_ratios: Dict[str, float],
        correlated_pairs: List[tuple[str, str]]
    ) -> Dict[str, float]:
        """Calculates Kelly allocations adjusted for maximum risk limits and correlation risk.

        Returns allocations for each asset and Cash remainder.
        """
        allocations = {}
        total_allocated = 0.0

        for asset in assets:
            w = win_rates.get(asset, 0.55)
            r = win_loss_ratios.get(asset, 1.5)
            
            # 1. Kelly Sizing
            kelly = self.calculate_kelly_fraction(w, r)
            
            # Risk limits boundary (e.g. limit each asset allocation to max_risk_pct * 15)
            allocated_pct = min(kelly, 0.50)  # cap individual asset allocation at 50%
            
            # Ensure risk is bounded
            max_asset_allocation = (self.max_risk_pct / 100.0) * 20.0
            allocated_pct = min(allocated_pct, max_asset_allocation)
            
            allocations[asset] = allocated_pct

        # 2. Correlation Risk Adjustment
        # If correlated assets are found in allocation list, reduce their allocations by 30%
        for asset1, asset2 in correlated_pairs:
            if asset1 in allocations and asset2 in allocations:
                # Apply 30% reduction to prevent correlation risk
                allocations[asset1] = round(allocations[asset1] * 0.7, 2)
                allocations[asset2] = round(allocations[asset2] * 0.7, 2)

        # Build final allocation dictionary
        final_allocations = {}
        for asset, alloc in allocations.items():
            final_allocations[asset] = round(alloc, 2)
            total_allocated += final_allocations[asset]

        # Allocate remainder to Cash
        cash = round(1.0 - total_allocated, 2)
        final_allocations["Cash"] = max(0.0, cash)

        return final_allocations
