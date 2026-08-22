"""OHLCV Candle Builder aggregating ticks into 1m, 5m, 15m, and 1h bars (Sprint 9B)."""

from __future__ import annotations

import collections
from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Dict, List, Optional, Tuple

from paper_trading.models.market_models import MarketCandle, MarketTick

logger = logging.getLogger(__name__)

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


class _ActiveCandle:
    """Internal mutable tracking state for an open candle bar."""

    def __init__(self, symbol: str, timeframe: str, open_time: datetime, close_time: datetime, first_tick: MarketTick) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.open_time = open_time
        self.close_time = close_time
        self.open = first_tick.price
        self.high = first_tick.price
        self.low = first_tick.price
        self.close = first_tick.price
        self.volume = first_tick.volume

    def update(self, tick: MarketTick) -> None:
        """Update candle values with incoming tick."""
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.volume

    def to_market_candle(self) -> MarketCandle:
        """Convert internal state to immutable MarketCandle."""
        return MarketCandle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            open_time=self.open_time,
            close_time=self.close_time,
        )


class CandleBuilder:
    """Thread-safe aggregator assembling ticks into 1m, 5m, 15m, and 1h OHLCV bars."""

    def __init__(
        self,
        timeframes: Optional[List[str]] = None,
        max_completed_candles: int = 1000,
    ) -> None:
        if max_completed_candles <= 0:
            raise ValueError(f"max_completed_candles must be positive, got {max_completed_candles}")

        self._lock = threading.RLock()
        self._timeframes = timeframes or ["1m", "5m", "15m", "1h"]
        self._max_completed_candles = max_completed_candles

        for tf in self._timeframes:
            if tf not in TIMEFRAME_SECONDS:
                raise ValueError(f"Unsupported timeframe: {tf}. Must be one of {list(TIMEFRAME_SECONDS.keys())}")

        # key: (symbol, timeframe) -> _ActiveCandle
        self._active_candles: Dict[Tuple[str, str], _ActiveCandle] = {}
        # key: (symbol, timeframe) -> deque[MarketCandle]
        self._completed_candles: Dict[Tuple[str, str], collections.deque[MarketCandle]] = {}

    def process_tick(self, tick: MarketTick) -> List[MarketCandle]:
        """Process incoming MarketTick and return list of completed MarketCandles closed during rollover."""
        closed_candles: List[MarketCandle] = []

        with self._lock:
            ts = tick.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            for tf in self._timeframes:
                interval_secs = TIMEFRAME_SECONDS[tf]
                open_ts, close_ts = self._calculate_bar_bounds(ts, interval_secs)

                key = (tick.symbol, tf)
                active = self._active_candles.get(key)

                if active is None:
                    # Initialize new open candle
                    self._active_candles[key] = _ActiveCandle(tick.symbol, tf, open_ts, close_ts, tick)
                elif ts >= active.close_time:
                    # Rollover: Close active candle
                    completed = active.to_market_candle()
                    closed_candles.append(completed)

                    if key not in self._completed_candles:
                        self._completed_candles[key] = collections.deque(maxlen=self._max_completed_candles)
                    self._completed_candles[key].append(completed)

                    # Start new open candle for tick
                    self._active_candles[key] = _ActiveCandle(tick.symbol, tf, open_ts, close_ts, tick)
                else:
                    # Update existing active candle
                    active.update(tick)

        return closed_candles

    def get_active_candle(self, symbol: str, timeframe: str) -> Optional[MarketCandle]:
        """Get current in-progress candle snapshot."""
        with self._lock:
            key = (symbol, timeframe)
            active = self._active_candles.get(key)
            return active.to_market_candle() if active else None

    def get_completed_candles(self, symbol: str, timeframe: str) -> List[MarketCandle]:
        """Get history of completed candles for symbol and timeframe."""
        with self._lock:
            key = (symbol, timeframe)
            return list(self._completed_candles.get(key, []))

    def _calculate_bar_bounds(self, ts: datetime, interval_secs: int) -> Tuple[datetime, datetime]:
        """Calculate start and end timestamps for time interval bar."""
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        total_seconds = int((ts - epoch).total_seconds())
        bar_start_seconds = (total_seconds // interval_secs) * interval_secs

        open_time = epoch + timedelta(seconds=bar_start_seconds)
        close_time = open_time + timedelta(seconds=interval_secs)
        return open_time, close_time
