"""Unit tests for the Price Action Engine repository."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
import pytest

from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.exceptions import RepositoryError
from price_action.core.models import (
    PatternMatch,
    PatternSnapshot,
    PatternState,
)
from price_action.core.repository import PriceActionRepository


class MockStorageEngine:
    """Mock storage engine simulating SQL query execution and raw rows writing."""

    def __init__(self) -> None:
        self.rows_written = []
        self.queries_executed = []
        self.should_raise = False

    def write_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        if self.should_raise:
            raise Exception("Mock DB Failure")
        self.rows_written.append((table, rows))

    def execute(self, query: str) -> list[dict[str, Any]]:
        if self.should_raise:
            raise Exception("Mock DB Query Failure")
        self.queries_executed.append(query)
        # Return a mock representation matching rows schema
        return []


def test_repository_in_memory_crud():
    """Verify standard CRUD and querying with memory-only repository fallback."""
    repo = PriceActionRepository()
    dt = datetime.now(timezone.utc)

    # 1. Loading non-existent snapshots
    assert repo.load_snapshot("snap-1") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None

    # 2. Saving snapshot
    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-1", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    repo.save_snapshot(snapshot)

    # 3. Load by ID
    loaded = repo.load_snapshot("snap-1")
    assert loaded is not None
    assert loaded.snapshot_id == "snap-1"

    # 4. Load latest
    latest = repo.load_latest_snapshot("BTCUSDT")
    assert latest is not None
    assert latest.snapshot_id == "snap-1"

    # 5. Get historical snapshots
    start = dt - timedelta(minutes=5)
    end = dt + timedelta(minutes=5)
    history = repo.get_historical_snapshots("BTCUSDT", start, end)
    assert len(history) == 1
    assert history[0].snapshot_id == "snap-1"


def test_repository_load_patterns_filtering():
    """Verify repository loading and pattern query filters in memory."""
    repo = PriceActionRepository()
    dt = datetime.now(timezone.utc)

    match = PatternMatch(
        match_id="m1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        fit_score=0.9,
        confirmed_at=dt,
    )

    state = PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_patterns=[match],
        historical_patterns=[],
        updated_at=dt,
    )
    snapshot = PatternSnapshot(snapshot_id="snap-1", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    repo.save_snapshot(snapshot)

    # Query all matches
    all_patterns = repo.load_patterns("BTCUSDT")
    assert len(all_patterns) == 1

    # Query with filters
    tops = repo.load_patterns("BTCUSDT", pattern_type=PatternType.DOUBLE_TOP, status=PatternStatus.CONFIRMED)
    assert len(tops) == 1
    assert tops[0].match_id == "m1"

    # Query with mismatch filters
    bottoms = repo.load_patterns("BTCUSDT", pattern_type=PatternType.DOUBLE_BOTTOM)
    assert len(bottoms) == 0


def test_repository_db_persistence():
    """Verify sql-storage integration when DB engine is provided."""
    storage = MockStorageEngine()
    repo = PriceActionRepository(storage_engine=storage)
    dt = datetime.now(timezone.utc)

    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-db-1", symbol="BTCUSDT", timestamp=dt, states={"1h": state})
    repo.save_snapshot(snapshot)

    # Assert writes routing
    assert len(storage.rows_written) == 1
    assert storage.rows_written[0][0] == "price_action_snapshots"
    assert storage.rows_written[0][1][0]["snapshot_id"] == "snap-db-1"


def test_repository_db_error_handling():
    """Verify repository exception handling on DB engine errors."""
    storage = MockStorageEngine()
    storage.should_raise = True
    repo = PriceActionRepository(storage_engine=storage)
    dt = datetime.now(timezone.utc)

    state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    snapshot = PatternSnapshot(snapshot_id="snap-err", symbol="BTCUSDT", timestamp=dt, states={"1h": state})

    with pytest.raises(RepositoryError):
        repo.save_snapshot(snapshot)
