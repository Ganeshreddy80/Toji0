"""Volatility Engine for measuring market volatility metrics."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

from market_intelligence.core.events import VolatilityUpdated
from market_intelligence.core.models import VolatilityAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class VolatilityEngine:
    """Calculates rolling ATR, historical/realized volatility, and Bollinger width."""

    def __init__(self, event_bus: IEventBus | None = None, window: int = 20) -> None:
        self._event_bus = event_bus
        self._window = window
        self._candles: dict[tuple[str, str], list[Any]] = {}
        self._atr_history: dict[tuple[str, str], list[float]] = {}
        self._realized_vols: dict[tuple[str, str], list[float]] = {}

    def calculate_volatility(self, candle: Any) -> VolatilityAnalysis:
        """Process a new candle and compute rolling volatility analysis."""
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._candles:
            self._candles[key] = []
            self._atr_history[key] = []
            self._realized_vols[key] = []

        history = self._candles[key]
        history.append(candle)
        if len(history) > 500:
            history.pop(0)

        n = len(history)
        closes = [c.close for c in history]

        # 1. ATR calculation
        if n == 1:
            tr = candle.high - candle.low
        else:
            prev = history[-2]
            tr = max(
                candle.high - candle.low,
                abs(candle.high - prev.close),
                abs(candle.low - prev.close)
            )
        
        # 14-period ATR
        atr_history = self._atr_history[key]
        if n < 14:
            atr = sum(
                max(
                    history[i].high - history[i].low,
                    abs(history[i].high - history[i-1].close) if i > 0 else 0.0,
                    abs(history[i].low - history[i-1].close) if i > 0 else 0.0
                ) for i in range(n)
            ) / n
        else:
            prev_atr = atr_history[-1] if atr_history else tr
            atr = (prev_atr * 13 + tr) / 14
        atr_history.append(atr)

        # 2. Historical & Realized Volatility
        hist_vol = 0.0
        realized_vol = 0.0
        if n >= 2:
            limit = min(n, self._window)
            returns = []
            log_returns = []
            for i in range(n - limit, n - 1):
                p_curr = closes[i+1]
                p_prev = closes[i]
                if p_prev > 0:
                    returns.append((p_curr - p_prev) / p_prev)
                    log_returns.append(math.log(p_curr / p_prev))
            
            if returns:
                mean_r = sum(returns) / len(returns)
                realized_vol = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
                
                mean_log = sum(log_returns) / len(log_returns)
                hist_vol = math.sqrt(sum((lr - mean_log) ** 2 for lr in log_returns) / len(log_returns))

        self._realized_vols[key].append(realized_vol)

        # 3. Bollinger Width
        bollinger_width = 0.0
        limit_boll = min(n, 20)
        if limit_boll > 1:
            recent_closes = closes[-limit_boll:]
            ma = sum(recent_closes) / limit_boll
            variance = sum((c - ma) ** 2 for c in recent_closes) / limit_boll
            stddev = math.sqrt(variance)
            if ma > 0:
                bollinger_width = (4.0 * stddev) / ma

        # 4. Volatility Percentile
        vol_pct = 50.0
        vols_hist = self._realized_vols[key]
        if len(vols_hist) > 1:
            hist_len = min(len(vols_hist), 100)
            comparison_set = vols_hist[-hist_len:]
            smaller_count = sum(1 for v in comparison_set if v < realized_vol)
            vol_pct = (smaller_count / hist_len) * 100.0

        # 5. Daily Range
        daily_range = candle.high - candle.low

        analysis = VolatilityAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            atr=atr,
            historical_volatility=hist_vol,
            realized_volatility=realized_vol,
            bollinger_width=bollinger_width,
            volatility_percentile=vol_pct,
            daily_range=daily_range,
            timestamp=candle.timestamp
        )

        self._publish_event(analysis)
        return analysis

    def _publish_event(self, analysis: VolatilityAnalysis) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "atr": analysis.atr,
            "historical_volatility": analysis.historical_volatility,
            "realized_volatility": analysis.realized_volatility,
            "bollinger_width": analysis.bollinger_width,
            "volatility_percentile": analysis.volatility_percentile,
            "daily_range": analysis.daily_range,
            "timestamp": analysis.timestamp.isoformat()
        }
        event = VolatilityUpdated(
            source="market_intelligence.volatility_engine",
            payload=payload
        )
        self._event_bus.publish(event)
