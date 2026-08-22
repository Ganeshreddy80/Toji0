"""Unit tests for the Trading Context Snapshot Repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from data.storage.base import MockPostgresStorageEngine
from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from trading_context.core.exceptions import RepositoryError
from trading_context.core.models import (
    TradingContext,
    TradingContextSnapshot,
)
from trading_context.core.repository import TradingContextRepository


@pytest.fixture
def dummy_context() -> TradingContext:
    """Create a dummy TradingContext for repository testing."""
    dt = datetime.now(timezone.utc)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=dt),
        strategy_state=StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt),
        generated_at=dt,
    )


def test_repository_in_memory_crud(dummy_context):
    """Verify in-memory CRUD operations on the repository."""
    repo = TradingContextRepository()
    now = datetime.now(timezone.utc)

    # Load non-existent
    assert repo.load_snapshot("not-found") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None
    assert repo.get_historical_snapshots("BTCUSDT", now, now) == []

    # Try saving invalid snapshot
    with pytest.raises(RepositoryError, match="valid ID and symbol"):
        repo.save_snapshot(
            TradingContextSnapshot(snapshot_id="", symbol="BTCUSDT", timestamp=now, states={})
        )

    # Prepare states
    s1 = TradingContextSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now - timedelta(seconds=10),
        states={"1h": dummy_context.model_copy(update={"generated_at": now - timedelta(seconds=10)})},
    )
    s2 = TradingContextSnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": dummy_context.model_copy(update={"generated_at": now})},
    )
    s3 = TradingContextSnapshot(
        snapshot_id="s3",
        symbol="BTCUSDT",
        timestamp=now + timedelta(seconds=10),
        states={"1h": dummy_context.model_copy(update={"generated_at": now + timedelta(seconds=10)})},
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


def test_repository_with_postgres_storage(dummy_context):
    """Verify repository backed by MockPostgresStorageEngine."""
    db = MockPostgresStorageEngine()
    db.connect()
    repo = TradingContextRepository(storage_engine=db)

    now = datetime.now(timezone.utc)
    s1 = TradingContextSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": dummy_context},
    )

    repo.save_snapshot(s1)

    # Verify row written to DB
    assert "trading_contexts" in db.tables
    assert len(db.tables["trading_contexts"]) == 1

    # Clear repository in-memory cache to force reading from database mock
    repo._by_id.clear()
    repo._by_symbol.clear()

    # Load by ID (db query)
    loaded = repo.load_snapshot("s1")
    assert loaded is not None
    assert loaded.snapshot_id == "s1"
    assert "1h" in loaded.states
    assert loaded.states["1h"].symbol == "BTCUSDT"
