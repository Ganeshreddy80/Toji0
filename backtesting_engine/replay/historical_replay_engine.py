"""Historical replay engine for sequential data stepping and timestamp control (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import List, Optional

from backtesting_engine.core.enums import ReplayStatus
from backtesting_engine.core.events import (
    HistoricalBarReplayed,
    ReplayCompleted,
    ReplayPaused,
    ReplayStarted,
)
from backtesting_engine.core.exceptions import ReplayError
from backtesting_engine.core.interfaces import IHistoricalReplayEngine
from backtesting_engine.core.models import MarketBar
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class HistoricalReplayEngine(IHistoricalReplayEngine):
    """Replays historical OHLCV market bars deterministically with event bus broadcasts."""

    def __init__(
        self,
        bars: Optional[List[MarketBar]] = None,
        event_bus: Optional[IEventBus] = None,
    ) -> None:
        self._bars: List[MarketBar] = sorted(bars or [], key=lambda b: b.timestamp)
        self._cursor: int = 0
        self._status: ReplayStatus = ReplayStatus.CREATED
        self._event_bus = event_bus

    def load_data(self, bars: List[MarketBar]) -> None:
        """Load and chronologically sort historical bar data."""
        if not bars:
            raise ReplayError("Cannot load empty market bar data.")
        self._bars = sorted(bars, key=lambda b: b.timestamp)
        self._cursor = 0
        self._status = ReplayStatus.CREATED

    def start(self) -> None:
        """Start or resume historical data replay."""
        if not self._bars:
            raise ReplayError("No market bar data loaded for replay.")
        self._status = ReplayStatus.RUNNING
        if self._event_bus:
            self._event_bus.publish(
                ReplayStarted(
                    source="backtesting.replay",
                    payload={"total_bars": len(self._bars), "start_time": self._bars[0].timestamp.isoformat()},
                )
            )

    def pause(self) -> None:
        """Pause data replay."""
        self._status = ReplayStatus.PAUSED
        if self._event_bus:
            self._event_bus.publish(
                ReplayPaused(
                    source="backtesting.replay",
                    payload={"cursor": self._cursor},
                )
            )

    def stop(self) -> None:
        """Stop replay and reset cursor."""
        self._status = ReplayStatus.STOPPED
        self._cursor = 0

    def step(self) -> Optional[MarketBar]:
        """Replay next single bar synchronously and broadcast HistoricalBarReplayed."""
        if self._cursor >= len(self._bars):
            if self._status != ReplayStatus.COMPLETED:
                self._status = ReplayStatus.COMPLETED
                if self._event_bus:
                    self._event_bus.publish(
                        ReplayCompleted(
                            source="backtesting.replay",
                            payload={"total_replayed": len(self._bars)},
                        )
                    )
            return None

        bar = self._bars[self._cursor]
        self._cursor += 1

        if self._event_bus:
            self._event_bus.publish(
                HistoricalBarReplayed(
                    source="backtesting.replay",
                    payload={"symbol": bar.symbol, "timestamp": bar.timestamp.isoformat(), "close": bar.close},
                )
            )

        if self._cursor >= len(self._bars):
            self._status = ReplayStatus.COMPLETED
            if self._event_bus:
                self._event_bus.publish(
                    ReplayCompleted(
                        source="backtesting.replay",
                        payload={"total_replayed": len(self._bars)},
                    )
                )

        return bar

    def seek(self, timestamp: datetime) -> bool:
        """Seek replay cursor to the first bar at or after target timestamp."""
        for idx, bar in enumerate(self._bars):
            if bar.timestamp >= timestamp:
                self._cursor = idx
                return True
        self._cursor = len(self._bars)
        return False

    @property
    def status(self) -> ReplayStatus:
        return self._status

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def total_bars(self) -> int:
        return len(self._bars)
