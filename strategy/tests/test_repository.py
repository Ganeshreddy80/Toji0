"""Unit tests for the Strategy Snapshot Repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from data.storage.base import MockPostgresStorageEngine
from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.exceptions import RepositoryError
from strategy.core.models import (
    StrategySnapshot,
    StrategyState,
    StrategySignal,
)
from strategy.core.repository import StrategyRepository


def create_dummy_signal(symbol: str, timeframe: str, decision: StrategyDecision) -> StrategySignal:
    """Create a dummy strategy signal for testing."""
    return StrategySignal(
        signal_id="sig-abc",
        symbol=symbol,
        timeframe=timeframe,
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=decision,
        confidence=80.0,
        confluence_score=85.0,
        reasoning="Dummy signal for testing.",
        supporting_factors=[],
        conflicting_factors=[],
        detected_at=datetime.now(timezone.utc),
    )


def test_repository_in_memory_crud():
    """Verify in-memory CRUD operations on the repository."""
    repo = StrategyRepository()
    now = datetime.now(timezone.utc)

    # Load non-existent
    assert repo.load_snapshot("not-found") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None
    assert repo.get_historical_snapshots("BTCUSDT", now, now) == []

    # Try saving invalid snapshot
    with pytest.raises(RepositoryError, match="valid ID and symbol"):
        repo.save_snapshot(
            StrategySnapshot(snapshot_id="", symbol="BTCUSDT", timestamp=now, states={})
        )

    # Prepare states
    state1 = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=create_dummy_signal("BTCUSDT", "1h", StrategyDecision.BUY),
        updated_at=now - timedelta(seconds=10),
    )
    state2 = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=create_dummy_signal("BTCUSDT", "1h", StrategyDecision.BUY),
        updated_at=now,
    )
    state3 = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=create_dummy_signal("BTCUSDT", "1h", StrategyDecision.BUY),
        updated_at=now + timedelta(seconds=10),
    )

    # Save snapshots
    s1 = StrategySnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now - timedelta(seconds=10),
        states={"1h": state1},
    )
    s2 = StrategySnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state2},
    )
    s3 = StrategySnapshot(
        snapshot_id="s3",
        symbol="BTCUSDT",
        timestamp=now + timedelta(seconds=10),
        states={"1h": state3},
    )

    repo.save_snapshot(s2)
    repo.save_snapshot(s1)  # Save out of order to verify sorting
    repo.save_snapshot(s3)

    # Verify loading by ID
    assert repo.load_snapshot("s1") == s1
    assert repo.load_snapshot("s2") == s2

    # Verify loading latest
    assert repo.load_latest_snapshot("BTCUSDT") == s3

    # Verify historical timeframe filtering and sorting
    history = repo.get_historical_snapshots(
        "BTCUSDT", now - timedelta(seconds=5), now + timedelta(seconds=15)
    )
    assert len(history) == 2
    assert [s.snapshot_id for s in history] == ["s2", "s3"]


def test_repository_with_postgres_storage():
    """Verify repository backed by MockPostgresStorageEngine."""
    db = MockPostgresStorageEngine()
    db.connect()
    repo = StrategyRepository(storage_engine=db)

    now = datetime.now(timezone.utc)
    state1 = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=create_dummy_signal("BTCUSDT", "1h", StrategyDecision.BUY),
        updated_at=now,
    )
    s1 = StrategySnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state1},
    )

    repo.save_snapshot(s1)

    # Verify row written to DB
    assert "strategy_snapshots" in db.tables
    assert len(db.tables["strategy_snapshots"]) == 1

    # Clear repository in-memory cache to force reading from database mock
    repo._by_id.clear()
    repo._by_symbol.clear()

    # Load by ID (db query)
    loaded = repo.load_snapshot("s1")
    assert loaded is not None
    assert loaded.snapshot_id == "s1"
    assert "1h" in loaded.states
    assert loaded.states["1h"].latest_signal.confidence == 0.8
