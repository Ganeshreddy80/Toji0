"""Portfolio volatility rebalancer adjusting leverage based on target risk."""

from __future__ import annotations

import logging
from typing import Dict, Any

from research_platform.portfolio_intelligence.models import RebalanceInstruction
from research_platform.portfolio_intelligence.risk_parity import RiskParityAllocator

logger = logging.getLogger(__name__)


class PortfolioRebalancer:
    """Manages target volatility allocations and rebalancing triggers."""

    def __init__(self, target_volatility: float = 0.12) -> None:
        self.target_volatility = target_volatility
        self._allocator = RiskParityAllocator()

    def generate_rebalance(self, assets_volatility: Dict[str, float], portfolio_volatility: float) -> RebalanceInstruction:
        """Determines target weights scaled to match the target volatility.

        If portfolio volatility is higher than target, scaling leverage factor is < 1.0.
        """
        base_weights = self._allocator.calculate_weights(assets_volatility)
        
        # Scaling leverage factor
        if portfolio_volatility > 0.0:
            leverage_scale = self.target_volatility / portfolio_volatility
        else:
            leverage_scale = 1.0

        # Scale weights according to target volatility
        target_weights = {}
        for asset, weight in base_weights.items():
            target_weights[asset] = weight * min(leverage_scale, 1.5)  # Cap leverage at 1.5x

        return RebalanceInstruction(
            target_weights=target_weights,
            volatility_target=self.target_volatility
        )
