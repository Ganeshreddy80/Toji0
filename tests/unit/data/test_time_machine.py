"""Unit tests for the Time Machine historical reconstruction replay interfaces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from data.time_machine.interfaces import ITimeMachine


class MockTimeMachine(ITimeMachine):
    """Mock implementation of the ITimeMachine interface for testing."""

    def __init__(self, start_time: datetime) -> None:
        self._current_time = start_time
        self.history: list[datetime] = []

    @property
    def current_time(self) -> datetime:
        return self._current_time

    def set_time(self, timestamp: datetime) -> None:
        self._current_time = timestamp

    def get_historical_snapshot(
        self, symbol: str, data_type: str, timestamp: datetime | None = None
    ) -> Any:
        t = timestamp or self._current_time
        return {"symbol": symbol, "data_type": data_type, "as_of": t}

    def replay(
        self,
        start_time: datetime,
        end_time: datetime,
        step_seconds: float,
        callback: Callable[[datetime], None],
    ) -> None:
        self._current_time = start_time
        callback(self._current_time)
        self.history.append(self._current_time)


def test_time_machine_interface():
    start = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    tm = MockTimeMachine(start)

    assert tm.current_time == start

    # Test snapshot lookup
    snap = tm.get_historical_snapshot("BTC/USDT", "ohlcv")
    assert snap["as_of"] == start
    assert snap["symbol"] == "BTC/USDT"

    # Test time adjustment
    future = datetime(2026, 6, 25, 13, 0, 0, tzinfo=UTC)
    tm.set_time(future)
    assert tm.current_time == future

    # Test replay loop trigger
    ticks = []
    tm.replay(start, future, 60.0, lambda t: ticks.append(t))
    assert len(ticks) == 1
    assert ticks[0] == start
