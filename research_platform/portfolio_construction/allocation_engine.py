"""Allocation engine creating portfolio allocation mappings.
"""

from __future__ import annotations

from typing import Dict
from research_platform.portfolio_construction.models import PortfolioAllocation


class AllocationEngine:
    """Instantiates weight allocations configurations."""

    def initiate_allocation(self, allocation_id: str, weights: Dict[str, float]) -> PortfolioAllocation:
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        normalized = {}
        if total > 0.0:
            normalized = {asset: w / total for asset, w in weights.items()}
        else:
            normalized = dict(weights)

        return PortfolioAllocation(
            allocation_id=allocation_id,
            weights=normalized
        )
