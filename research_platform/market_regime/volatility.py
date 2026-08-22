"""Volatility regime detector class implementing IVolatilityDetector.
"""

from __future__ import annotations

import logging
import math
from typing import List
from research_platform.market_regime.interfaces import IVolatilityDetector
from research_platform.market_regime.models import VolatilityRegime

logger = logging.getLogger(__name__)


class VolatilityDetector(IVolatilityDetector):
    """Classifies volatility regimes using relative standard deviation and ATR indicators."""

    def detect_volatility(self, prices: List[float], atr_values: List[float]) -> VolatilityRegime:
        """Classify volatility into LOW, NORMAL, or HIGH."""
        if not prices:
            return VolatilityRegime.NORMAL

        # If ATR is provided, we can evaluate relative ATR
        if atr_values and len(atr_values) > 0:
            avg_atr = sum(atr_values) / len(atr_values)
            avg_price = sum(prices) / len(prices)
            rel_atr = avg_atr / avg_price if avg_price > 0 else 0.0
            
            if rel_atr > 0.03:
                return VolatilityRegime.HIGH
            elif rel_atr < 0.01:
                return VolatilityRegime.LOW
            else:
                return VolatilityRegime.NORMAL

        # Fallback to standard deviation of prices
        n = len(prices)
        if n < 2:
            return VolatilityRegime.NORMAL

        mean = sum(prices) / n
        variance = sum((p - mean) ** 2 for p in prices) / (n - 1)
        std_dev = math.sqrt(variance)
        rel_vol = std_dev / mean if mean > 0 else 0.0

        if rel_vol > 0.04:
            return VolatilityRegime.HIGH
        elif rel_vol < 0.015:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.NORMAL
