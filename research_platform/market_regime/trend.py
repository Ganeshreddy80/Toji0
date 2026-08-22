"""Trend regime detector class implementing ITrendDetector.
"""

from __future__ import annotations

import logging
from typing import List
from research_platform.market_regime.interfaces import ITrendDetector
from research_platform.market_regime.models import RegimeType

logger = logging.getLogger(__name__)


class TrendDetector(ITrendDetector):
    """Classifies trend regimes using price slope and simple moving averages crossovers."""

    def detect_trend(self, prices: List[float]) -> RegimeType:
        """Classify trend direction into BULLISH, BEARISH, or RANGEBOUND."""
        if not prices or len(prices) < 5:
            return RegimeType.RANGEBOUND

        # Compute moving average of prices
        sma = sum(prices) / len(prices)
        last_price = prices[-1]
        
        # Calculate momentum slope over last few ticks
        short_window = prices[-3:]
        slope = short_window[-1] - short_window[0]

        # Determine trend
        rel_diff = (last_price - sma) / sma if sma > 0 else 0.0

        if rel_diff > 0.01 and slope > 0:
            return RegimeType.BULLISH
        elif rel_diff < -0.01 and slope < 0:
            return RegimeType.BEARISH
        else:
            return RegimeType.RANGEBOUND
