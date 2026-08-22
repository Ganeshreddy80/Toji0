"""Institutional Order Block (OB) detector."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import PatternDirection, SwingType
from price_action.core.interfaces import IOrderBlockDetector
from price_action.core.models import (
    OrderBlock,
    PriceActionBar,
    PriceActionConfig,
    PriceActionSwing,
)

logger = logging.getLogger(__name__)


class OrderBlockDetector(IOrderBlockDetector):
    """Detects bullish and bearish institutional Order Blocks."""

    def detect_order_blocks(
        self, bars: List[PriceActionBar], swings: List[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> List[OrderBlock]:
        """Identify Order Blocks preceding displacement moves and evaluate mitigation."""
        if not bars or len(bars) < 3:
            return []

        cfg = config or PriceActionConfig()
        surge_mult = cfg.ob_volume_surge_mult
        obs: List[OrderBlock] = []
        n = len(bars)

        # Average volume baseline
        volumes = [b.volume for b in bars if b.volume > 0]
        avg_vol = sum(volumes) / len(volumes) if volumes else 1.0

        for i in range(1, n - 1):
            c_prev = bars[i - 1]
            c_curr = bars[i]
            c_next = bars[i + 1]

            # Bullish OB: c_curr is bearish candle followed by strong bullish expansion
            if c_curr.close < c_curr.open and c_next.close > c_curr.high:
                move_size = c_next.close - c_curr.low
                body_size = abs(c_curr.close - c_curr.open)
                vol_ratio = (c_next.volume / avg_vol) if avg_vol > 0 else 1.0

                if move_size > body_size * 1.5 and vol_ratio >= surge_mult:
                    is_mitigated = any(bars[j].low <= c_curr.high for j in range(i + 2, n))
                    obs.append(
                        OrderBlock(
                            ob_id=f"ob-bullish-{c_curr.index}",
                            direction=PatternDirection.BULLISH,
                            top=c_curr.high,
                            bottom=c_curr.low,
                            high=c_curr.high,
                            low=c_curr.low,
                            volume_surge=round(vol_ratio, 2),
                            created_at=c_curr.timestamp,
                            is_mitigated=is_mitigated,
                        )
                    )

            # Bearish OB: c_curr is bullish candle followed by strong bearish expansion
            elif c_curr.close > c_curr.open and c_next.close < c_curr.low:
                move_size = c_curr.high - c_next.close
                body_size = abs(c_curr.close - c_curr.open)
                vol_ratio = (c_next.volume / avg_vol) if avg_vol > 0 else 1.0

                if move_size > body_size * 1.5 and vol_ratio >= surge_mult:
                    is_mitigated = any(bars[j].high >= c_curr.low for j in range(i + 2, n))
                    obs.append(
                        OrderBlock(
                            ob_id=f"ob-bearish-{c_curr.index}",
                            direction=PatternDirection.BEARISH,
                            top=c_curr.high,
                            bottom=c_curr.low,
                            high=c_curr.high,
                            low=c_curr.low,
                            volume_surge=round(vol_ratio, 2),
                            created_at=c_curr.timestamp,
                            is_mitigated=is_mitigated,
                        )
                    )

        return obs
