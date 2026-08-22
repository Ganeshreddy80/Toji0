"""Market structure detector analyzing BOS, CHOCH, and structural trend bias."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import MarketStructureType, SwingType, TrendDirection
from price_action.core.interfaces import IMarketStructureDetector
from price_action.core.models import (
    MarketStructureState,
    PriceActionBar,
    PriceActionConfig,
    PriceActionSwing,
)

logger = logging.getLogger(__name__)


class MarketStructureDetector(IMarketStructureDetector):
    """Detects market structure shifts (CHOCH) and continuations (BOS)."""

    def detect_market_structure(
        self, bars: List[PriceActionBar], swings: List[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> MarketStructureState:
        """Analyze swing sequence and candle closes to determine market structure state."""
        if not swings or not bars:
            return MarketStructureState(
                trend_bias=TrendDirection.SIDEWAYS,
                last_structure_type=None,
                last_bos_price=None,
                last_choch_price=None,
                recent_swings=[],
            )

        swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
        swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]

        trend_bias = TrendDirection.SIDEWAYS
        last_structure = None
        last_bos = None
        last_choch = None

        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            prev_sh, latest_sh = swing_highs[-2], swing_highs[-1]
            prev_sl, latest_sl = swing_lows[-2], swing_lows[-1]

            if latest_sh.price > prev_sh.price and latest_sl.price > prev_sl.price:
                trend_bias = TrendDirection.BULLISH
                last_structure = MarketStructureType.BOS
                last_bos = latest_sh.price
            elif latest_sh.price < prev_sh.price and latest_sl.price < prev_sl.price:
                trend_bias = TrendDirection.BEARISH
                last_structure = MarketStructureType.BOS
                last_bos = latest_sl.price
            elif latest_sh.price > prev_sh.price and latest_sl.price < prev_sl.price:
                trend_bias = TrendDirection.SIDEWAYS
                last_structure = MarketStructureType.RANGE
            elif latest_sh.price < prev_sh.price and latest_sl.price > prev_sl.price:
                trend_bias = TrendDirection.SIDEWAYS
                last_structure = MarketStructureType.RANGE

        # Check latest candle break for CHOCH / BOS against latest swing level
        if bars and swings:
            last_close = bars[-1].close
            recent_sh = max(swings, key=lambda s: s.price if s.swing_type == SwingType.SWING_HIGH else 0.0)
            recent_sl = min(swings, key=lambda s: s.price if s.swing_type == SwingType.SWING_LOW else float("inf"))

            if last_close > recent_sh.price and trend_bias == TrendDirection.BEARISH:
                trend_bias = TrendDirection.BULLISH
                last_structure = MarketStructureType.CHOCH
                last_choch = recent_sh.price
            elif last_close < recent_sl.price and trend_bias == TrendDirection.BULLISH:
                trend_bias = TrendDirection.BEARISH
                last_structure = MarketStructureType.CHOCH
                last_choch = recent_sl.price

        return MarketStructureState(
            trend_bias=trend_bias,
            last_structure_type=last_structure,
            last_bos_price=last_bos,
            last_choch_price=last_choch,
            recent_swings=swings[-10:],
        )
