"""Historical Event Replay Engine.
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone
from typing import Generator, List, Optional

from research_platform.backtesting_engine.models import MarketEvent, SimulationClock


class HistoricalReplayEngine:
    """Replays historical market events in strict temporal order, updating SimulationClock."""

    def __init__(self, df: pd.DataFrame, symbol: str, event_type: str = "OHLCV") -> None:
        """Initialize replay data.

        Expected DataFrame columns: timestamp, open, high, low, close, volume.
        """
        self._df = df.sort_values("timestamp").reset_index(drop=True)
        self._symbol = symbol
        self._event_type = event_type
        self._index = 0
        self._paused = False

        # Initialize SimulationClock
        first_time = pd.to_datetime(self._df["timestamp"].iloc[0]).to_pydatetime() if not self._df.empty else datetime.now(timezone.utc)
        if first_time.tzinfo is None:
            first_time = first_time.replace(tzinfo=timezone.utc)
        self._clock = SimulationClock(current_time=first_time)

    @property
    def clock(self) -> SimulationClock:
        return self._clock

    def set_time(self, target_time: datetime) -> None:
        """Time travel to a specific starting date."""
        target = target_time
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)

        # Find closest index where timestamp is >= target_time
        timestamps = pd.to_datetime(self._df["timestamp"]).dt.tz_localize(None)
        target_naive = target.replace(tzinfo=None)
        matches = self._df[timestamps >= target_naive]
        if not matches.empty:
            self._index = int(matches.index[0])
            self._clock = SimulationClock(current_time=target)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def has_next(self) -> bool:
        return self._index < len(self._df)

    def next_event(self) -> Optional[MarketEvent]:
        """Step forward and retrieve the next MarketEvent."""
        if self._paused or not self.has_next():
            return None

        row = self._df.iloc[self._index]
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        self._index += 1
        self._clock = SimulationClock(current_time=ts)

        # Pack data dictionary
        data_dict = {
            "open": float(row.get("open", 0.0)),
            "high": float(row.get("high", 0.0)),
            "low": float(row.get("low", 0.0)),
            "close": float(row.get("close", 0.0)),
            "volume": float(row.get("volume", 0.0))
        }

        # Handle ask/bid spread variables if present
        if "ask" in row:
            data_dict["ask"] = float(row["ask"])
        if "bid" in row:
            data_dict["bid"] = float(row["bid"])

        return MarketEvent(
            timestamp=ts,
            symbol=self._symbol,
            event_type=self._event_type,
            data=data_dict
        )
