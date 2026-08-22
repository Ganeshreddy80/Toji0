"""Trend Engine for tracking Bullish, Bearish, and Ranging trends."""

from __future__ import annotations

import logging
from datetime import datetime

from market_intelligence.core.enums import SwingType, TrendDirection
from market_intelligence.core.events import TrendChanged, TrendAnalyzed
from market_intelligence.core.models import StructurePoint, TrendState, TrendAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class TrendEngine:
    """Calculates Trend direction and strength from confirmed swing points and moving averages."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Mapping: (symbol, timeframe) -> current trend state (string)
        self._current_trends: dict[tuple[str, str], str] = {}
        # Mapping: (symbol, timeframe) -> TrendState
        self._trend_states: dict[tuple[str, str], TrendState] = {}
        # Mapping: (symbol, timeframe) -> Pydantic TrendAnalysis
        self._pydantic_trends: dict[tuple[str, str], TrendAnalysis] = {}
        # Histoy of close prices
        self._closes: dict[tuple[str, str], list[float]] = {}
        # History of EMA values
        self._ema_histories: dict[tuple[str, str], dict[int, list[float]]] = {}
        # History of calculated slopes
        self._slopes: dict[tuple[str, str], list[float]] = {}

    def get_trend_state(self, symbol: str, timeframe: str) -> TrendState | None:
        """Get the active TrendState or None if UNKNOWN."""
        return self._trend_states.get((symbol, timeframe))

    def get_trend_direction(self, symbol: str, timeframe: str) -> str:
        """Get the current trend direction string ("BULLISH", "BEARISH", "RANGING", "UNKNOWN")."""
        return self._current_trends.get((symbol, timeframe), "UNKNOWN")

    def get_pydantic_trend(self, symbol: str, timeframe: str) -> TrendAnalysis | None:
        """Get the current Pydantic TrendAnalysis model."""
        return self._pydantic_trends.get((symbol, timeframe))

    def _update_ema(self, key: tuple[str, str], period: int, price: float) -> float:
        if key not in self._ema_histories:
            self._ema_histories[key] = {}
        if period not in self._ema_histories[key]:
            self._ema_histories[key][period] = []
        
        history = self._ema_histories[key][period]
        if not history:
            ema = price
        else:
            prev_ema = history[-1]
            k = 2.0 / (period + 1.0)
            ema = (price * k) + (prev_ema * (1.0 - k))
        
        history.append(ema)
        if len(history) > 500:
            history.pop(0)
        return ema

    def evaluate_trend(
        self,
        symbol: str,
        timeframe: str,
        structure_history: list[StructurePoint],
        timestamp: datetime,
        candle: Any | None = None,
    ) -> TrendState | None:
        """Evaluate and update the trend state based on swing history and price indicators."""
        key = (symbol, timeframe)

        highs = [
            p.swing_point
            for p in structure_history
            if p.swing_point.point_type == SwingType.HIGH
        ]
        lows = [
            p.swing_point
            for p in structure_history
            if p.swing_point.point_type == SwingType.LOW
        ]

        old_trend = self._current_trends.get(key, "UNKNOWN")
        new_trend = "UNKNOWN"

        if len(highs) >= 2 and len(lows) >= 2:
            sh_n = highs[-1]
            sh_prev = highs[-2]
            sl_n = lows[-1]
            sl_prev = lows[-2]

            # Bullish: HH and HL
            if sh_n.price > sh_prev.price and sl_n.price > sl_prev.price:
                new_trend = "BULLISH"
            # Bearish: LH and LL
            elif sh_n.price < sh_prev.price and sl_n.price < sl_prev.price:
                new_trend = "BEARISH"
            else:
                new_trend = "RANGING"
        else:
            new_trend = "UNKNOWN"

        # If trend direction changed or is initialized
        if new_trend != old_trend:
            self._current_trends[key] = new_trend
            self._publish_trend_event(
                symbol, timeframe, old_trend, new_trend, timestamp
            )

        # Create or update TrendState
        if new_trend == "UNKNOWN":
            self._trend_states.pop(key, None)
            return None

        direction = TrendDirection.SIDEWAYS
        if new_trend == "BULLISH":
            direction = TrendDirection.UP
        elif new_trend == "BEARISH":
            direction = TrendDirection.DOWN

        strength = 1.0 if new_trend in ("BULLISH", "BEARISH") else 0.5

        # Check if we keep start_time from previous state
        start_time = timestamp
        prev_state = self._trend_states.get(key)
        if prev_state and prev_state.direction == direction:
            start_time = prev_state.start_time

        trend_state = TrendState(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            start_time=start_time,
            end_time=timestamp,
        )
        self._trend_states[key] = trend_state

        # --- Sprint 5 Calculations ---
        price = candle.close if candle is not None else 0.0
        
        # Track closes
        if key not in self._closes:
            self._closes[key] = []
        closes = self._closes[key]
        closes.append(price)
        if len(closes) > 500:
            closes.pop(0)

        # 1. EMA Calculations
        ema20 = self._update_ema(key, 20, price)
        ema50 = self._update_ema(key, 50, price)
        ema100 = self._update_ema(key, 100, price)
        ema200 = self._update_ema(key, 200, price)

        # 2. Slope & Acceleration
        slope = 0.0
        accel = 0.0
        if len(closes) >= 2:
            prev_price = closes[-2]
            slope = (price - prev_price) / prev_price if prev_price > 0.0 else 0.0
            
            if key not in self._slopes:
                self._slopes[key] = []
            slopes = self._slopes[key]
            slopes.append(slope)
            if len(slopes) > 100:
                slopes.pop(0)
            
            if len(slopes) >= 2:
                accel = slopes[-1] - slopes[-2]

        # 3. Duration bars
        duration_bars = len(closes) # simple duration in active bars

        trend_analysis = TrendAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            duration_bars=duration_bars,
            slope=slope,
            acceleration=accel,
            ema20=ema20,
            ema50=ema50,
            ema100=ema100,
            ema200=ema200,
            start_time=start_time,
            end_time=timestamp,
        )
        self._pydantic_trends[key] = trend_analysis
        self._publish_trend_analyzed(trend_analysis)

        return trend_state

    def _publish_trend_event(
        self,
        symbol: str,
        timeframe: str,
        old_trend: str,
        new_trend: str,
        timestamp: datetime,
    ) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "old_trend": old_trend,
            "new_trend": new_trend,
            "timestamp": timestamp.isoformat(),
        }

        event = TrendChanged(
            source="market_intelligence.trend_engine", payload=payload
        )
        self._event_bus.publish(event)

    def _publish_trend_analyzed(self, analysis: TrendAnalysis) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "direction": analysis.direction.value,
            "strength": analysis.strength,
            "duration_bars": analysis.duration_bars,
            "slope": analysis.slope,
            "acceleration": analysis.acceleration,
            "ema20": analysis.ema20,
            "ema50": analysis.ema50,
            "ema100": analysis.ema100,
            "ema200": analysis.ema200,
            "timestamp": analysis.end_time.isoformat()
        }
        event = TrendAnalyzed(
            source="market_intelligence.trend_engine",
            payload=payload
        )
        self._event_bus.publish(event)
