"""Liquidity regime detector class implementing ILiquidityDetector.
"""

from __future__ import annotations

import logging
from typing import List
from research_platform.market_regime.interfaces import ILiquidityDetector
from research_platform.market_regime.models import LiquidityRegime

logger = logging.getLogger(__name__)


class LiquidityDetector(ILiquidityDetector):
    """Classifies liquidity regimes using volume indicators and spread ranges."""

    def detect_liquidity(self, volumes: List[float], spreads: List[float]) -> LiquidityRegime:
        """Classify liquidity into LOW, NORMAL, or HIGH."""
        if not spreads:
            if volumes:
                avg_vol = sum(volumes) / len(volumes)
                if avg_vol < 1000.0:
                    return LiquidityRegime.LOW
                elif avg_vol > 50000.0:
                    return LiquidityRegime.HIGH
                else:
                    return LiquidityRegime.NORMAL
            return LiquidityRegime.NORMAL

        avg_spread = sum(spreads) / len(spreads)

        # Enforce spread rules
        if avg_spread > 0.005:  # Spread > 50bps -> Illiquid / Low Liquidity
            return LiquidityRegime.LOW
        elif avg_spread < 0.001:  # Spread < 10bps -> High Liquidity
            return LiquidityRegime.HIGH
        else:
            return LiquidityRegime.NORMAL
