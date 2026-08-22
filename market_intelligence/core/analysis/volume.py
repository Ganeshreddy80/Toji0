"""Volume Context Engine for calculating volume profiles and ATR."""

from __future__ import annotations

import logging
import math
from typing import Any

from market_intelligence.core.enums import VolumeExpansionState
from market_intelligence.core.events import VolumeContextUpdated
from market_intelligence.core.models import VolumeState
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class VolumeContextEngine:
    """Calculates rolling ATR, volume SMA, Relative Volume, and expansion states."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        self._candles: dict[tuple[str, str], list[Any]] = {}
        self._tr_history: dict[tuple[str, str], list[float]] = {}
        self._atr_history: dict[tuple[str, str], list[float]] = {}
        self._volume_states: dict[tuple[str, str], VolumeState] = {}

    def get_atr(self, symbol: str, timeframe: str) -> float:
        """Get the current ATR value or 0.0 if not computed."""
        key = (symbol, timeframe)
        history = self._atr_history.get(key)
        return history[-1] if history else 0.0

    def get_volume_state(self, symbol: str, timeframe: str) -> VolumeState | None:
        """Retrieve the current volume state."""
        return self._volume_states.get((symbol, timeframe))

    def process_candle(self, candle: Any) -> VolumeState:
        """Update historical tracking and compute volume analytics for the new candle."""
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._candles:
            self._candles[key] = []
            self._tr_history[key] = []
            self._atr_history[key] = []

        history = self._candles[key]
        history.append(candle)
        n = len(history)

        # 1. Calculate True Range (TR)
        if n == 1:
            tr = candle.high - candle.low
        else:
            prev_candle = history[-2]
            tr = max(
                candle.high - candle.low,
                abs(candle.high - prev_candle.close),
                abs(candle.low - prev_candle.close),
            )
        self._tr_history[key].append(tr)

        # 2. Calculate Average True Range (ATR)
        if n < 14:
            atr = sum(self._tr_history[key]) / n
        elif n == 14:
            atr = sum(self._tr_history[key][:14]) / 14
        else:
            prev_atr = self._atr_history[key][-1]
            atr = (prev_atr * 13 + tr) / 14
        self._atr_history[key].append(atr)

        # 3. Rolling Volume SMA and Standard Deviation (20-period window)
        window = min(n, 20)
        vols = [c.volume for c in history[-window:]]
        mean_vol = sum(vols) / window

        if window > 1:
            variance = sum((v - mean_vol) ** 2 for v in vols) / window
            stddev_vol = math.sqrt(variance)
        else:
            stddev_vol = 0.0

        # 4. RVOL (Relative Volume)
        rvol = candle.volume / mean_vol if mean_vol > 0.0 else 1.0

        # 5. Volume Expansion State
        is_climatic = (candle.volume > mean_vol + 3.0 * stddev_vol) if stddev_vol > 0.0 else False

        if is_climatic:
            exp_state = VolumeExpansionState.CLIMATIC
        elif rvol > 2.0:
            exp_state = VolumeExpansionState.EXPANSION
        else:
            exp_state = VolumeExpansionState.NORMAL

        vol_state = VolumeState(
            symbol=symbol,
            timeframe=timeframe,
            volume_ma=mean_vol,
            normalized_volume=rvol,
            expansion_state=exp_state,
            atr=atr,
        )
        self._volume_states[key] = vol_state

        # 6. Publish Event
        self._publish_event(vol_state, candle.timestamp)

        return vol_state

    def _publish_event(self, state: VolumeState, timestamp: Any) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": state.symbol,
            "timeframe": state.timeframe,
            "volume_ma": state.volume_ma,
            "normalized_volume": state.normalized_volume,
            "expansion_state": state.expansion_state.value,
            "timestamp": timestamp.isoformat(),
        }

        event = VolumeContextUpdated(
            source="market_intelligence.volume_context_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
