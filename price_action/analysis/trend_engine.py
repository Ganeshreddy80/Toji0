"""Trend analysis engine for the Price Action Engine."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import TrendDirection
from price_action.core.interfaces import ITrendEngine
from price_action.core.models import PriceActionBar, PriceActionConfig, TrendMetrics

logger = logging.getLogger(__name__)


class TrendEngine(ITrendEngine):
    """Evaluates moving average alignment, price position, and trend direction/strength."""

    def analyze_trend(
        self, bars: List[PriceActionBar], config: PriceActionConfig | None = None
    ) -> TrendMetrics:
        """Calculate fast/slow MAs, alignment, direction, and strength score."""
        if not bars:
            return TrendMetrics()

        cfg = config or PriceActionConfig()
        fast_p = cfg.fast_ma_period
        slow_p = cfg.slow_ma_period

        closes = [b.close for b in bars]
        n = len(closes)

        if n < fast_p:
            return TrendMetrics(
                direction=TrendDirection.SIDEWAYS,
                strength=0.0,
                fast_ma=closes[-1] if closes else 0.0,
                slow_ma=closes[-1] if closes else 0.0,
                is_aligned=False,
            )

        fast_ma = sum(closes[-fast_p:]) / fast_p
        slow_p_effective = min(n, slow_p)
        slow_ma = sum(closes[-slow_p_effective:]) / slow_p_effective

        curr_price = closes[-1]
        is_bullish_ma = fast_ma > slow_ma
        is_bearish_ma = fast_ma < slow_ma
        is_price_above = curr_price > fast_ma
        is_price_below = curr_price < fast_ma

        direction = TrendDirection.SIDEWAYS
        is_aligned = False
        strength = 0.0

        diff_pct = abs(fast_ma - slow_ma) / (slow_ma if slow_ma > 0 else 1.0)
        strength = min(1.0, round(diff_pct * 20.0, 4))

        if is_bullish_ma and is_price_above:
            direction = TrendDirection.BULLISH
            is_aligned = True
            strength = min(1.0, round(strength + 0.3, 4))
        elif is_bearish_ma and is_price_below:
            direction = TrendDirection.BEARISH
            is_aligned = True
            strength = min(1.0, round(strength + 0.3, 4))
        elif is_bullish_ma:
            direction = TrendDirection.BULLISH
        elif is_bearish_ma:
            direction = TrendDirection.BEARISH

        return TrendMetrics(
            direction=direction,
            strength=strength,
            fast_ma=round(fast_ma, 4),
            slow_ma=round(slow_ma, 4),
            is_aligned=is_aligned,
        )
