"""Historical tick replayer and replication error variance calculator engine implementing IMarketReplayer.
"""

from __future__ import annotations

import logging
from typing import List
from research_platform.simulation.interfaces import IMarketReplayer
from research_platform.simulation.models import ReplayConfiguration, SimTick

logger = logging.getLogger(__name__)


class MarketReplayer(IMarketReplayer):
    """Replays historical tick logs sequentially, applying stress testing multipliers."""

    def replay_ticks(self, ticks: List[SimTick], config: ReplayConfiguration) -> List[SimTick]:
        """Stress test and return price feeds incorporating volatility multipliers."""
        if not ticks:
            return []

        vol_mult = config.stress_params.volatility_multiplier
        if vol_mult == 1.0:
            return ticks

        stressed_ticks = []
        base_price = ticks[0].price

        for tick in ticks:
            # Volatility shift: scale deviation from first base price
            deviation = tick.price - base_price
            stressed_price = base_price + (deviation * vol_mult)
            
            stressed_ticks.append(tick.model_copy(update={
                "price": stressed_price
            }))

        logger.info("Stressed price feed: Volatility scaled by %.2f x across %d ticks.",
                    vol_mult, len(ticks))
        return stressed_ticks

    def calculate_replication_error(self, actual_returns: List[float], simulated_returns: List[float]) -> float:
        """Calculate mean squared error variance between returns vectors."""
        n = min(len(actual_returns), len(simulated_returns))
        if n == 0:
            return 0.0

        squared_diff_sum = sum((act - sim) ** 2 for act, sim in zip(actual_returns[:n], simulated_returns[:n]))
        error = squared_diff_sum / n
        
        logger.info("Calculated simulation replication error variance: %.8f", error)
        return error
