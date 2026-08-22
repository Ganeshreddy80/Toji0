"""Momentum engine calculating RSI, MACD, and momentum divergence."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import DivergenceType, SwingType
from price_action.core.interfaces import IMomentumEngine
from price_action.core.models import (
    MomentumMetrics,
    PriceActionBar,
    PriceActionConfig,
    PriceActionSwing,
)

logger = logging.getLogger(__name__)


class MomentumEngine(IMomentumEngine):
    """Calculates RSI, MACD, and detects bullish/bearish momentum divergences."""

    def analyze_momentum(
        self, bars: List[PriceActionBar], swings: List[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> MomentumMetrics:
        """Calculate RSI, MACD, and momentum divergence against price swings."""
        if not bars:
            return MomentumMetrics()

        cfg = config or PriceActionConfig()
        closes = [b.close for b in bars]
        n = len(closes)

        if n < 14:
            return MomentumMetrics(rsi=50.0, macd=0.0, macd_signal=0.0, macd_histogram=0.0, divergence=DivergenceType.NONE)

        # 1. Calculate RSI (14 period)
        rsi_p = cfg.rsi_period
        gains: List[float] = []
        losses: List[float] = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))

        avg_gain = sum(gains[-rsi_p:]) / rsi_p if len(gains) >= rsi_p else 0.0
        avg_loss = sum(losses[-rsi_p:]) / rsi_p if len(losses) >= rsi_p else 0.0

        if avg_loss == 0.0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # 2. Calculate MACD
        fast_p = cfg.macd_fast
        slow_p = cfg.macd_slow
        signal_p = cfg.macd_signal

        ema_fast = self._calculate_ema(closes, fast_p)
        ema_slow = self._calculate_ema(closes, slow_p)
        macd = ema_fast - ema_slow

        # Estimate signal line as SMA of recent MACD values proxy
        macd_hist_proxy = 0.0
        macd_signal = 0.0
        if len(closes) >= slow_p + signal_p:
            macd_series = []
            for k in range(slow_p, len(closes) + 1):
                sub_closes = closes[:k]
                ef = self._calculate_ema(sub_closes, fast_p)
                es = self._calculate_ema(sub_closes, slow_p)
                macd_series.append(ef - es)

            macd_signal = sum(macd_series[-signal_p:]) / len(macd_series[-signal_p:])
            macd_hist_proxy = macd - macd_signal

        # 3. Detect Divergence
        divergence = DivergenceType.NONE
        swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]
        swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]

        if len(swing_lows) >= 2:
            s1, s2 = swing_lows[-2], swing_lows[-1]
            if s2.price < s1.price and rsi > 40.0:  # Price lower low, RSI higher (bullish div)
                divergence = DivergenceType.BULLISH_DIVERGENCE
        elif len(swing_highs) >= 2:
            s1, s2 = swing_highs[-2], swing_highs[-1]
            if s2.price > s1.price and rsi < 60.0:  # Price higher high, RSI lower (bearish div)
                divergence = DivergenceType.BEARISH_DIVERGENCE

        return MomentumMetrics(
            rsi=round(max(0.0, min(100.0, rsi)), 2),
            macd=round(macd, 4),
            macd_signal=round(macd_signal, 4),
            macd_histogram=round(macd_hist_proxy, 4),
            divergence=divergence,
        )

    def _calculate_ema(self, values: List[float], period: int) -> float:
        if not values:
            return 0.0
        if len(values) < period:
            return sum(values) / len(values)
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for val in values[period:]:
            ema = (val * k) + (ema * (1.0 - k))
        return ema
