"""Unit tests for Historical Replay Engine (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from backtesting_engine.core.enums import ReplayStatus
from backtesting_engine.core.events import HistoricalBarReplayed, ReplayCompleted, ReplayStarted
from backtesting_engine.core.exceptions import ReplayError
from backtesting_engine.replay.historical_replay_engine import HistoricalReplayEngine
from backtesting_engine.core.models import MarketBar
from toji_platform.core.event_bus import InMemoryEventBus


def create_sample_bars() -> list[MarketBar]:
    return [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49500.0, close=50500.0, volume=10.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=50500.0, high=52000.0, low=50000.0, close=51500.0, volume=15.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), open=51500.0, high=51800.0, low=49000.0, close=49200.0, volume=20.0),
    ]


def test_replay_stepping_and_sorting():
    bars = create_sample_bars()
    engine = HistoricalReplayEngine(bars=bars)

    assert engine.total_bars == 3
    assert engine.status == ReplayStatus.CREATED

    engine.start()
    assert engine.status == ReplayStatus.RUNNING

    b1 = engine.step()
    assert b1 is not None
    assert b1.timestamp == datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert engine.cursor == 1

    b2 = engine.step()
    assert b2 is not None
    assert b2.timestamp == datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc)

    b3 = engine.step()
    assert b3 is not None
    assert b3.timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert engine.status == ReplayStatus.COMPLETED

    b4 = engine.step()
    assert b4 is None


def test_replay_pause_stop_seek():
    bars = create_sample_bars()
    engine = HistoricalReplayEngine(bars=bars)
    engine.start()

    engine.step()
    engine.pause()
    assert engine.status == ReplayStatus.PAUSED

    found = engine.seek(datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc))
    assert found is True
    assert engine.cursor == 2

    engine.stop()
    assert engine.status == ReplayStatus.STOPPED
    assert engine.cursor == 0


def test_replay_event_publication():
    event_bus = InMemoryEventBus()
    events_captured = []

    event_bus.subscribe(ReplayStarted().event_type, lambda e: events_captured.append(e))
    event_bus.subscribe(HistoricalBarReplayed().event_type, lambda e: events_captured.append(e))
    event_bus.subscribe(ReplayCompleted().event_type, lambda e: events_captured.append(e))

    bars = create_sample_bars()
    engine = HistoricalReplayEngine(bars=bars, event_bus=event_bus)
    engine.start()

    engine.step()
    engine.step()
    engine.step()

    assert len(events_captured) == 5  # 1 Started + 3 Replayed + 1 Completed
    assert isinstance(events_captured[0], ReplayStarted)
    assert isinstance(events_captured[1], HistoricalBarReplayed)
    assert isinstance(events_captured[-1], ReplayCompleted)
