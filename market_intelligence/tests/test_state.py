"""Unit tests for the MIL State Store."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
import pytest

from market_intelligence.core.enums import TrendDirection
from market_intelligence.core.exceptions import StateStoreError
from market_intelligence.core.models import MarketSnapshot, TrendState
from market_intelligence.core.state import MarketIntelligenceState


def test_state_store_basic_operations():
    """Verify basic storage, retrieval, history, and clear."""
    store = MarketIntelligenceState(history_limit=5)
    now = datetime.now(timezone.utc)

    # Empty store
    assert store.get_snapshot("BTCUSDT") is None
    assert store.get_history("BTCUSDT") == []

    # Save snapshot
    snap1 = MarketSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    store.update_snapshot(snap1)
    assert store.get_snapshot("BTCUSDT") == snap1
    assert store.get_history("BTCUSDT") == [snap1]

    # Save a second snapshot for history
    snap2 = MarketSnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    store.update_snapshot(snap2)
    assert store.get_snapshot("BTCUSDT") == snap2
    assert store.get_history("BTCUSDT") == [snap1, snap2]

    # Test clearing
    store.clear()
    assert store.get_snapshot("BTCUSDT") is None
    assert store.get_history("BTCUSDT") == []


def test_state_store_history_limits():
    """Verify that history deques respect limits."""
    store = MarketIntelligenceState(history_limit=3)
    now = datetime.now(timezone.utc)

    snaps = [
        MarketSnapshot(
            snapshot_id=f"s{i}", symbol="BTCUSDT", timestamp=now, states={}
        )
        for i in range(5)
    ]

    for snap in snaps:
        store.update_snapshot(snap)

    history = store.get_history("BTCUSDT", limit=10)
    assert len(history) == 3
    # Check that it kept the latest 3 snapshots
    assert [s.snapshot_id for s in history] == ["s2", "s3", "s4"]

    # Retrieve with a custom smaller limit
    sub_history = store.get_history("BTCUSDT", limit=2)
    assert len(sub_history) == 2
    assert [s.snapshot_id for s in sub_history] == ["s3", "s4"]


def test_state_store_invalid_symbol_raises():
    """Verify updating with empty symbol raises StateStoreError."""
    store = MarketIntelligenceState()
    snap = MarketSnapshot(
        snapshot_id="s1",
        symbol="",
        timestamp=datetime.now(timezone.utc),
        states={},
    )
    with pytest.raises(StateStoreError, match="valid symbol"):
        store.update_snapshot(snap)


def test_state_store_incremental_timeframe_update():
    """Verify incremental timeframe updates apply to the active snapshot."""
    store = MarketIntelligenceState()
    now = datetime.now(timezone.utc)

    # Cannot update if snapshot does not exist
    with pytest.raises(StateStoreError, match="No active snapshot found"):
        store.update_timeframe_state("BTCUSDT", "1h", "dummy_state")

    # Create initial snapshot
    initial_snap = MarketSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    store.update_snapshot(initial_snap)

    # Perform incremental update
    trend_state = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.9,
        start_time=now,
        end_time=now,
    )

    updated_snap = store.update_timeframe_state("BTCUSDT", "1h", trend_state)
    assert updated_snap.symbol == "BTCUSDT"
    assert "1h" in updated_snap.states
    assert updated_snap.states["1h"] == trend_state

    # Verify it updated active snapshot and history
    active = store.get_snapshot("BTCUSDT")
    assert active == updated_snap
    assert len(store.get_history("BTCUSDT")) == 2


def test_state_store_thread_safety():
    """Verify concurrent updates work without raising race condition issues."""
    store = MarketIntelligenceState()
    now = datetime.now(timezone.utc)

    initial_snap = MarketSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    store.update_snapshot(initial_snap)

    threads = []
    errors = []

    def updater(timeframe_str: str):
        try:
            trend_state = TrendState(
                symbol="BTCUSDT",
                timeframe=timeframe_str,
                direction=TrendDirection.UP,
                strength=0.5,
                start_time=now,
                end_time=now,
            )
            store.update_timeframe_state("BTCUSDT", timeframe_str, trend_state)
        except Exception as e:
            errors.append(e)

    # Spawn 50 threads updating different timeframes
    for i in range(50):
        t = threading.Thread(target=updater, args=(f"tf_{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert not errors, f"Encountered thread safety errors: {errors}"
    final_snap = store.get_snapshot("BTCUSDT")
    assert final_snap is not None
    assert len(final_snap.states) == 50
