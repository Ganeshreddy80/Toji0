"""Swing Engine for identifying Swing Highs and Swing Lows."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import SwingType
from market_intelligence.core.events import SwingHighConfirmed, SwingLowConfirmed
from market_intelligence.core.models import SwingPoint
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class SwingEngine:
    """Detects Swing Highs and Swing Lows with confirmation delay (t + k)."""

    def __init__(self, event_bus: IEventBus | None = None, k: int = 2) -> None:
        self._event_bus = event_bus
        self._k = k
        # Mapping: (symbol, timeframe) -> list of candle objects
        self._candles: dict[tuple[str, str], list[Any]] = {}
        # Mapping: (symbol, timeframe) -> list of confirmed SwingPoint
        self._swings: dict[tuple[str, str], list[SwingPoint]] = {}

    def get_swings(self, symbol: str, timeframe: str) -> list[SwingPoint]:
        """Get the list of confirmed swing points so far."""
        return self._swings.get((symbol, timeframe), [])

    def process_candle(self, candle: Any) -> SwingPoint | None:
        """Process a single candle (streaming update).

        Returns the confirmed swing point if one is confirmed on this bar, else None.
        """
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._candles:
            self._candles[key] = []
            self._swings[key] = []

        history = self._candles[key]
        history.append(candle)

        n = len(history) - 1
        t = n - self._k

        if t < self._k:
            return None

        # Check for Swing High / Swing Low at index t
        target_candle = history[t]
        is_high = True
        is_low = True

        for i in range(1, self._k + 1):
            # Left side check (non-strict)
            if target_candle.high < history[t - i].high:
                is_high = False
            # Right side check (strict to handle ties)
            if target_candle.high <= history[t + i].high:
                is_high = False

            if target_candle.low > history[t - i].low:
                is_low = False
            if target_candle.low >= history[t + i].low:
                is_low = False

        confirmed_point: SwingPoint | None = None

        if is_high:
            confirmed_point = SwingPoint(
                symbol=symbol,
                timeframe=timeframe,
                point_type=SwingType.HIGH,
                price=target_candle.high,
                timestamp=target_candle.timestamp,
                index=t,
            )
        elif is_low:
            confirmed_point = SwingPoint(
                symbol=symbol,
                timeframe=timeframe,
                point_type=SwingType.LOW,
                price=target_candle.low,
                timestamp=target_candle.timestamp,
                index=t,
            )

        if confirmed_point:
            self._swings[key].append(confirmed_point)
            self._publish_swing_event(confirmed_point)
            return confirmed_point

        return None

    def _publish_swing_event(self, swing: SwingPoint) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": swing.symbol,
            "timeframe": swing.timeframe,
            "price": swing.price,
            "index": swing.index,
            "timestamp": swing.timestamp.isoformat(),
        }

        if swing.point_type == SwingType.HIGH:
            event = SwingHighConfirmed(
                source="market_intelligence.swing_engine", payload=payload
            )
        else:
            event = SwingLowConfirmed(
                source="market_intelligence.swing_engine", payload=payload
            )

        self._event_bus.publish(event)
