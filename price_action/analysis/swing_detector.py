"""Swing pivot point detector for the Price Action Engine."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import SwingType
from price_action.core.interfaces import ISwingDetector
from price_action.core.models import PriceActionBar, PriceActionConfig, PriceActionSwing

logger = logging.getLogger(__name__)


class SwingDetector(ISwingDetector):
    """Detects pivot highs and pivot lows across candle bars."""

    def detect_swings(
        self, bars: List[PriceActionBar], config: PriceActionConfig | None = None
    ) -> List[PriceActionSwing]:
        """Identify swing pivot points using configurable left/right lookback."""
        if not bars:
            return []

        cfg = config or PriceActionConfig()
        lb = cfg.swing_lookback
        n = len(bars)
        swings: List[PriceActionSwing] = []

        if n < (2 * lb + 1):
            return swings

        for i in range(lb, n - lb):
            bar = bars[i]
            # Check Pivot High
            left_highs = [bars[i - k].high for k in range(1, lb + 1)]
            right_highs = [bars[i + k].high for k in range(1, lb + 1)]
            if bar.high >= max(left_highs) and bar.high > max(right_highs):
                swings.append(
                    PriceActionSwing(
                        swing_type=SwingType.SWING_HIGH,
                        price=bar.high,
                        timestamp=bar.timestamp,
                        index=bar.index,
                        strength=lb,
                    )
                )

            # Check Pivot Low
            left_lows = [bars[i - k].low for k in range(1, lb + 1)]
            right_lows = [bars[i + k].low for k in range(1, lb + 1)]
            if bar.low <= min(left_lows) and bar.low < min(right_lows):
                swings.append(
                    PriceActionSwing(
                        swing_type=SwingType.SWING_LOW,
                        price=bar.low,
                        timestamp=bar.timestamp,
                        index=bar.index,
                        strength=lb,
                    )
                )

        # Sort chronologically by bar index
        swings.sort(key=lambda s: s.index)
        return swings
