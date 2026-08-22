"""Volatility engine evaluating ATR, Bollinger Bands, and squeeze states."""

from __future__ import annotations

import logging
import math
from typing import List

from price_action.core.interfaces import IVolatilityEngine
from price_action.core.models import PriceActionBar, PriceActionConfig, VolatilityMetrics

logger = logging.getLogger(__name__)


class VolatilityEngine(IVolatilityEngine):
    """Calculates Average True Range (ATR), Bollinger Bands, and volatility squeeze conditions."""

    def analyze_volatility(
        self, bars: List[PriceActionBar], config: PriceActionConfig | None = None
    ) -> VolatilityMetrics:
        """Calculate ATR, Bollinger Bands, bandwidth ratio, and squeeze state."""
        if not bars:
            return VolatilityMetrics()

        cfg = config or PriceActionConfig()
        atr_p = cfg.atr_period
        bb_p = cfg.bb_period
        bb_std = cfg.bb_std_dev
        n = len(bars)

        if n < 2:
            return VolatilityMetrics(
                atr=0.0,
                atr_percent=0.0,
                bb_upper=bars[-1].close,
                bb_lower=bars[-1].close,
                bb_middle=bars[-1].close,
                bb_bandwidth=0.0,
                is_squeeze=False,
            )

        # 1. Calculate ATR
        true_ranges: List[float] = []
        for i in range(1, n):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        atr_calc_count = min(len(true_ranges), atr_p)
        atr = sum(true_ranges[-atr_calc_count:]) / atr_calc_count if atr_calc_count > 0 else 0.0
        curr_price = bars[-1].close
        atr_pct = (atr / curr_price) if curr_price > 0 else 0.0

        # 2. Calculate Bollinger Bands
        bb_calc_count = min(n, bb_p)
        recent_closes = [b.close for b in bars[-bb_calc_count:]]
        mean = sum(recent_closes) / bb_calc_count
        variance = sum((c - mean) ** 2 for c in recent_closes) / bb_calc_count
        std_dev = math.sqrt(variance)

        upper = mean + (bb_std * std_dev)
        lower = mean - (bb_std * std_dev)
        bandwidth = ((upper - lower) / mean) if mean > 0 else 0.0
        is_squeeze = bandwidth < 0.04  # Squeeze threshold (bandwidth under 4%)

        return VolatilityMetrics(
            atr=round(atr, 4),
            atr_percent=round(atr_pct, 4),
            bb_upper=round(upper, 4),
            bb_lower=round(lower, 4),
            bb_middle=round(mean, 4),
            bb_bandwidth=round(bandwidth, 4),
            is_squeeze=is_squeeze,
        )
