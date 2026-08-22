"""Unit tests for the Price Action Engine state store."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import pytest

from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.exceptions import StateStoreError
from price_action.core.models import (
    PatternMatch,
    PatternSnapshot,
    PatternState,
)
from price_action.core.state import PriceActionStateStore


def test_state_store_basic_operations():
    """Verify standard snapshot updating, retrieving, and clearing operations."""
    store = PriceActionStateStore(history_limit=5)
    dt = datetime.now(timezone.utc)

    # 1. Fetching non-existent snapshot
    assert store.get_snapshot("BTCUSDT") is None

    # 2. Update snapshot
    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-1", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    store.update_snapshot(snapshot)

    retrieved = store.get_snapshot("BTCUSDT")
    assert retrieved is not None
    assert retrieved.snapshot_id == "snap-1"
    assert retrieved.states["1h"].symbol == "BTCUSDT"

    # 3. Update timeframe state incrementally
    updated_state = PatternState(symbol="BTCUSDT", timeframe="15m", updated_at=dt)
    new_snapshot = store.update_timeframe_state("BTCUSDT", "15m", updated_state)

    assert "15m" in new_snapshot.states
    assert "1h" in new_snapshot.states

    # 4. Clear store
    store.clear()
    assert store.get_snapshot("BTCUSDT") is None


def test_state_store_history_limits():
    """Verify the rolling deque limit of state store snapshots."""
    store = PriceActionStateStore(history_limit=3)
    dt = datetime.now(timezone.utc)

    # Create empty baseline snapshot
    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-init", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    store.update_snapshot(snapshot)

    # Apply 4 timeframe updates
    for i in range(4):
        upd_state = PatternState(symbol="BTCUSDT", timeframe=f"1h-{i}", updated_at=dt)
        store.update_timeframe_state("BTCUSDT", f"1h-{i}", upd_state)

    history = store.get_history("BTCUSDT", limit=10)
    assert len(history) == 3  # Capped at history_limit = 3


def test_state_store_invalid_symbol_raises():
    """Verify validation limits in StateStore updates."""
    store = PriceActionStateStore()
    dt = datetime.now(timezone.utc)

    invalid_snapshot = PatternSnapshot(snapshot_id="snap-err", symbol="", timestamp=dt, states={})
    with pytest.raises(StateStoreError):
        store.update_snapshot(invalid_snapshot)


def test_state_store_query_filters():
    """Verify query filtering by pattern type and status on matches."""
    store = PriceActionStateStore()
    dt = datetime.now(timezone.utc)

    match1 = PatternMatch(
        match_id="m1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        fit_score=0.9,
        confirmed_at=dt,
    )
    match2 = PatternMatch(
        match_id="m2",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_BOTTOM,
        direction=PatternDirection.BULLISH,
        status=PatternStatus.COMPLETED,
        fit_score=0.95,
        confirmed_at=dt,
        completed_at=dt,
    )

    state = PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_patterns=[match1],
        historical_patterns=[match2],
        updated_at=dt,
    )
    snapshot = PatternSnapshot(snapshot_id="snap-1", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    store.update_snapshot(snapshot)

    # Query all matches
    all_matches = store.query("BTCUSDT")
    assert len(all_matches) == 2

    # Query with pattern type filter
    double_tops = store.query("BTCUSDT", pattern_type=PatternType.DOUBLE_TOP)
    assert len(double_tops) == 1
    assert double_tops[0].match_id == "m1"

    # Query with status filter
    completed_matches = store.query("BTCUSDT", status=PatternStatus.COMPLETED)
    assert len(completed_matches) == 1
    assert completed_matches[0].match_id == "m2"


def test_state_store_thread_safety():
    """Verify thread-safety of the state store under parallel write contention."""
    store = PriceActionStateStore()
    dt = datetime.now(timezone.utc)

    # Initalize store snapshot
    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-init", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    store.update_snapshot(snapshot)

    def write_task(idx: int):
        upd_state = PatternState(symbol="BTCUSDT", timeframe=f"tf-{idx}", updated_at=dt)
        store.update_timeframe_state("BTCUSDT", f"tf-{idx}", upd_state)

    # Concurrently write 20 times
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_task, i) for i in range(20)]
        for f in futures:
            f.result()

    snap = store.get_snapshot("BTCUSDT")
    assert snap is not None
    # 20 concurrent timeframe state updates plus initial 1h = 21 states
    assert len(snap.states) == 21
