"""Rebalancer compiling execution orders based on weight shifts.
"""

from __future__ import annotations

from typing import Dict, List
from research_platform.portfolio_construction.models import RebalanceOrder


class Rebalancer:
    """Calculates order sides based on target weight changes."""

    def compile_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float]
    ) -> List[RebalanceOrder]:
        orders = []
        all_assets = set(current_weights.keys()).union(target_weights.keys())

        for asset in all_assets:
            curr = current_weights.get(asset, 0.0)
            target = target_weights.get(asset, 0.0)
            
            if target > curr:
                side = "BUY"
            elif target < curr:
                side = "SELL"
            else:
                side = "HOLD"

            orders.append(RebalanceOrder(
                symbol=asset,
                target_weight=target,
                current_weight=curr,
                order_side=side
            ))

        return orders
