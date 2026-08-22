"""Multi-Timeframe Engine for calculating trend alignment and confirmations."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import TrendDirection
from market_intelligence.core.events import TimeframeAlignmentUpdated
from market_intelligence.core.interfaces import IStateStore
from market_intelligence.core.models import TimeframeAlignment
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MultiTimeframeEngine:
    """Tracks and evaluates trend alignment across 1m, 5m, 15m, 1h, 4h, and 1d timeframes."""

    TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

    def __init__(self, state_store: IStateStore | None = None, event_bus: IEventBus | None = None) -> None:
        self._state_store = state_store
        self._event_bus = event_bus

    def process_alignment(
        self,
        symbol: str,
        current_timeframe: str,
        current_trend_dir: str | None,
        timestamp: Any,
    ) -> TimeframeAlignment:
        """Fetch other timeframes' states, compute alignment/conflict, and higher TF confirmation."""
        # 1. Retrieve latest snapshot from state store
        snapshot = None
        if self._state_store is not None:
            snapshot = self._state_store.get_snapshot(symbol)

        # Standardize current trend direction string to "UP", "DOWN", "SIDEWAYS"
        if current_trend_dir == "BULLISH":
            current_val = "UP"
        elif current_trend_dir == "BEARISH":
            current_val = "DOWN"
        else:
            current_val = "SIDEWAYS"

        timeframe_trends: dict[str, str] = {}
        for tf in self.TIMEFRAMES:
            if tf == current_timeframe:
                timeframe_trends[tf] = current_val
            else:
                if snapshot is not None and tf in snapshot.states:
                    state = snapshot.states[tf]
                    if state.trend is not None:
                        timeframe_trends[tf] = state.trend.direction.value
                    else:
                        timeframe_trends[tf] = "SIDEWAYS"
                else:
                    timeframe_trends[tf] = "SIDEWAYS"

        # 2. Calculate Dominant Trend
        counts = {
            TrendDirection.UP: 0,
            TrendDirection.DOWN: 0,
            TrendDirection.SIDEWAYS: 0,
        }
        for tf, val in timeframe_trends.items():
            if val == "UP":
                counts[TrendDirection.UP] += 1
            elif val == "DOWN":
                counts[TrendDirection.DOWN] += 1
            else:
                counts[TrendDirection.SIDEWAYS] += 1

        max_count = max(counts.values())
        candidates = [k for k, v in counts.items() if v == max_count]
        
        if len(candidates) == 1:
            dominant_trend = candidates[0]
        else:
            # Tie breaker: Highest timeframe's trend wins
            dominant_trend = TrendDirection.SIDEWAYS
            for tf in reversed(self.TIMEFRAMES):
                tf_val = timeframe_trends.get(tf, "SIDEWAYS")
                tf_dir = TrendDirection.UP if tf_val == "UP" else (TrendDirection.DOWN if tf_val == "DOWN" else TrendDirection.SIDEWAYS)
                if tf_dir in candidates:
                    dominant_trend = tf_dir
                    break

        # 3. Calculate Scores
        n_tf = len(self.TIMEFRAMES)
        alignment_score = counts[dominant_trend] / n_tf

        if dominant_trend == TrendDirection.UP:
            conflict_score = counts[TrendDirection.DOWN] / n_tf
        elif dominant_trend == TrendDirection.DOWN:
            conflict_score = counts[TrendDirection.UP] / n_tf
        else:
            conflict_score = 0.0

        # 4. Higher Timeframe Confirmation
        # Locate current timeframe's position
        try:
            curr_idx = self.TIMEFRAMES.index(current_timeframe)
        except ValueError:
            curr_idx = -1

        if curr_idx == -1 or curr_idx == len(self.TIMEFRAMES) - 1:
            # Highest timeframe has confirmation = True by definition
            higher_confirmation = True
        else:
            higher_tf = self.TIMEFRAMES[curr_idx + 1]
            higher_val = timeframe_trends.get(higher_tf, "SIDEWAYS")
            higher_confirmation = (higher_val == current_val)

        alignment = TimeframeAlignment(
            dominant_trend=dominant_trend,
            alignment_score=alignment_score,
            conflict_score=conflict_score,
            higher_timeframe_confirmation=higher_confirmation,
            timeframe_trends=timeframe_trends,
        )

        # 5. Publish Event
        self._publish_event(symbol, current_timeframe, alignment, timestamp)

        return alignment

    def _publish_event(self, symbol: str, timeframe: str, alignment: TimeframeAlignment, timestamp: Any) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "dominant_trend": alignment.dominant_trend.value,
            "alignment_score": alignment.alignment_score,
            "conflict_score": alignment.conflict_score,
            "higher_confirmation": alignment.higher_timeframe_confirmation,
            "timeframe_trends": alignment.timeframe_trends,
            "timestamp": timestamp.isoformat(),
        }
        event = TimeframeAlignmentUpdated(
            source="market_intelligence.mtf_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
