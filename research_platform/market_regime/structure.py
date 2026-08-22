"""Market structure analyzer class implementing IMarketStructureAnalyzer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from research_platform.market_regime.interfaces import IMarketStructureAnalyzer
from research_platform.market_regime.models import MarketStructure

logger = logging.getLogger(__name__)


class MarketStructureAnalyzer(IMarketStructureAnalyzer):
    """Identifies support/resistance lines, breakouts, and candle order blocks."""

    def analyze_structure(self, prices: List[float], highs: List[float], lows: List[float]) -> MarketStructure:
        """Locate levels and breakouts in prices."""
        if not prices:
            return MarketStructure(symbol="unknown")

        support = []
        resistance = []
        breakouts = []

        # Simple pivot point detection
        n = len(prices)
        for i in range(2, n - 2):
            # Support: local minimum
            if prices[i] <= prices[i-1] and prices[i] <= prices[i-2] and prices[i] <= prices[i+1] and prices[i] <= prices[i+2]:
                support.append(prices[i])
            # Resistance: local maximum
            if prices[i] >= prices[i-1] and prices[i] >= prices[i-2] and prices[i] >= prices[i+1] and prices[i] >= prices[i+2]:
                resistance.append(prices[i])

        # Ensure uniqueness and sort
        support = sorted(list(set(support)))
        resistance = sorted(list(set(resistance)))

        # Breakout checks
        last_price = prices[-1]
        if resistance and last_price > max(resistance):
            breakouts.append("BULLISH_BREAKOUT")
        if support and last_price < min(support):
            breakouts.append("BEARISH_BREAKOUT")

        # Mock order block detection
        order_blocks = {
            "bullish_block": {"price": min(prices), "volume": 12000.0},
            "bearish_block": {"price": max(prices), "volume": 15000.0}
        }

        return MarketStructure(
            symbol="unknown",  # Symbol updated at orchestrator level
            support_levels=support,
            resistance_levels=resistance,
            breakouts=breakouts,
            order_blocks=order_blocks
        )
