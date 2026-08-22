"""Market State Machine classifying market structure phases."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import BOSRecord, CHoCHRecord, StructurePoint

logger = logging.getLogger(__name__)


class MarketStateMachine:
    """Manages rule-based market phase states and transitions."""

    def __init__(self) -> None:
        # Mapping: (symbol, timeframe) -> current state name (string)
        self._states: dict[tuple[str, str], str] = {}

    def get_state(self, symbol: str, timeframe: str) -> str:
        return self._states.get((symbol, timeframe), "Unknown")

    def update_state(
        self,
        symbol: str,
        timeframe: str,
        trend_direction: str,  # "BULLISH", "BEARISH", "RANGING", "UNKNOWN"
        structure_history: list[StructurePoint],
        bos: BOSRecord | None,
        choch: CHoCHRecord | None,
        current_candle: Any,
        prev_candle: Any | None = None,
    ) -> str:
        key = (symbol, timeframe)
        current_state = self._states.get(key, "Unknown")
        new_state = current_state

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

        # 1. Direct Trend overrides
        if trend_direction == "UNKNOWN":
            new_state = "Unknown"
        elif trend_direction == "BULLISH" and current_state not in (
            "Bull Trend",
            "Bull Pullback",
            "Bull Continuation",
        ):
            new_state = "Bull Trend"
        elif trend_direction == "BEARISH" and current_state not in (
            "Bear Trend",
            "Bear Pullback",
            "Bear Continuation",
        ):
            new_state = "Bear Trend"
        elif trend_direction == "RANGING" and current_state not in (
            "Accumulation",
            "Distribution",
        ):
            if current_state in ("Bull Trend", "Bull Pullback", "Bull Continuation"):
                new_state = "Distribution"
            elif current_state in (
                "Bear Trend",
                "Bear Pullback",
                "Bear Continuation",
            ):
                new_state = "Accumulation"
            else:
                new_state = "Accumulation"  # Default fallback

        # 2. Refined transition gates based on breakouts and candle closes
        close_price = current_candle.close

        if new_state in ("Bull Trend", "Bull Pullback", "Bull Continuation"):
            # CHoCH breaks low -> Distribution
            if choch is not None and choch.direction == "BULLISH_TO_BEARISH":
                new_state = "Distribution"
            # BOS breaks high -> Bull Continuation
            elif bos is not None and bos.direction == "UP":
                new_state = "Bull Continuation"
            # Retracement checking
            elif highs and lows:
                sh_last = highs[-1]
                sl_last = lows[-1]
                if (
                    prev_candle is not None
                    and close_price < prev_candle.close
                    and close_price < sh_last.price
                    and close_price > sl_last.price
                ):
                    new_state = "Bull Pullback"

        elif new_state in ("Bear Trend", "Bear Pullback", "Bear Continuation"):
            # CHoCH breaks high -> Accumulation
            if choch is not None and choch.direction == "BEARISH_TO_BULLISH":
                new_state = "Accumulation"
            # BOS breaks low -> Bear Continuation
            elif bos is not None and bos.direction == "DOWN":
                new_state = "Bear Continuation"
            # Retracement checking
            elif highs and lows:
                sh_last = highs[-1]
                sl_last = lows[-1]
                if (
                    prev_candle is not None
                    and close_price > prev_candle.close
                    and close_price > sl_last.price
                    and close_price < sh_last.price
                ):
                    new_state = "Bear Pullback"

        elif new_state == "Accumulation":
            if bos is not None and bos.direction == "UP":
                new_state = "Bull Continuation"
            elif trend_direction == "BULLISH":
                new_state = "Bull Trend"

        elif new_state == "Distribution":
            if bos is not None and bos.direction == "DOWN":
                new_state = "Bear Continuation"
            elif trend_direction == "BEARISH":
                new_state = "Bear Trend"

        self._states[key] = new_state
        return new_state
