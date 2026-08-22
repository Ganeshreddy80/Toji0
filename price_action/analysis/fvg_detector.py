"""Fair Value Gap (FVG) detector for 3-candle imbalance gaps."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import PatternDirection
from price_action.core.interfaces import IFairValueGapDetector
from price_action.core.models import FairValueGap, PriceActionBar, PriceActionConfig

logger = logging.getLogger(__name__)


class FairValueGapDetector(IFairValueGapDetector):
    """Detects Bullish and Bearish Fair Value Gaps (FVGs) and tracks mitigation."""

    def detect_fvgs(
        self, bars: List[PriceActionBar], config: PriceActionConfig | None = None
    ) -> List[FairValueGap]:
        """Identify 3-candle imbalance gaps and evaluate fill/mitigation status."""
        if not bars or len(bars) < 3:
            return []

        cfg = config or PriceActionConfig()
        min_gap_pct = cfg.fvg_min_gap_pct
        fvgs: List[FairValueGap] = []
        n = len(bars)

        for i in range(2, n):
            c1 = bars[i - 2]
            c2 = bars[i - 1]
            c3 = bars[i]

            # Bullish FVG: c1.high < c3.low
            if c3.low > c1.high:
                gap_size = c3.low - c1.high
                if (gap_size / c1.high) >= min_gap_pct:
                    bottom = c1.high
                    top = c3.low
                    midpoint = bottom + (top - bottom) / 2.0
                    fvg_id = f"fvg-bullish-{c2.index}"

                    # Check mitigation by subsequent candles (i+1 .. n-1)
                    is_mitigated = False
                    mitigated_at = None
                    for j in range(i + 1, n):
                        if bars[j].low <= midpoint:
                            is_mitigated = True
                            mitigated_at = bars[j].timestamp
                            break

                    fvgs.append(
                        FairValueGap(
                            fvg_id=fvg_id,
                            direction=PatternDirection.BULLISH,
                            top=top,
                            bottom=bottom,
                            midpoint=midpoint,
                            created_at=c2.timestamp,
                            is_mitigated=is_mitigated,
                            mitigated_at=mitigated_at,
                        )
                    )

            # Bearish FVG: c1.low > c3.high
            elif c1.low > c3.high:
                gap_size = c1.low - c3.high
                if (gap_size / c3.high) >= min_gap_pct:
                    top = c1.low
                    bottom = c3.high
                    midpoint = bottom + (top - bottom) / 2.0
                    fvg_id = f"fvg-bearish-{c2.index}"

                    # Check mitigation by subsequent candles
                    is_mitigated = False
                    mitigated_at = None
                    for j in range(i + 1, n):
                        if bars[j].high >= midpoint:
                            is_mitigated = True
                            mitigated_at = bars[j].timestamp
                            break

                    fvgs.append(
                        FairValueGap(
                            fvg_id=fvg_id,
                            direction=PatternDirection.BEARISH,
                            top=top,
                            bottom=bottom,
                            midpoint=midpoint,
                            created_at=c2.timestamp,
                            is_mitigated=is_mitigated,
                            mitigated_at=mitigated_at,
                        )
                    )

        return fvgs
