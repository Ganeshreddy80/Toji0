"""Unit tests for the Market Intelligence Repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from data.storage.base import MockPostgresStorageEngine
from market_intelligence.core.exceptions import RepositoryException
from market_intelligence.core.models import MarketSnapshot
from market_intelligence.core.repository import MarketIntelligenceRepository


def test_repo_in_memory_crud():
    """Verify in-memory save, load, latest load, and history lookup."""
    repo = MarketIntelligenceRepository()
    now = datetime.now(timezone.utc)

    # Load non-existent
    assert repo.load_snapshot("not-found") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None
    assert repo.get_historical_snapshots("BTCUSDT", now, now) == []

    # Try saving invalid snapshot
    with pytest.raises(RepositoryException, match="valid ID and symbol"):
        repo.save_snapshot(
            MarketSnapshot(snapshot_id="", symbol="BTCUSDT", timestamp=now, states={})
        )

    # Save snapshots
    s1 = MarketSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now - timedelta(seconds=10),
        states={},
    )
    s2 = MarketSnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    s3 = MarketSnapshot(
        snapshot_id="s3",
        symbol="BTCUSDT",
        timestamp=now + timedelta(seconds=10),
        states={},
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


def test_repo_with_postgres_storage():
    """Verify repository backed by MockPostgresStorageEngine."""
    db = MockPostgresStorageEngine()
    db.connect()
    repo = MarketIntelligenceRepository(storage_engine=db)

    now = datetime.now(timezone.utc)
    s1 = MarketSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now - timedelta(seconds=5),
        states={},
    )
    s2 = MarketSnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )

    repo.save_snapshot(s1)
    repo.save_snapshot(s2)

    # Verify rows written to the DB mock
    assert "market_intelligence_snapshots" in db.tables
    assert len(db.tables["market_intelligence_snapshots"]) == 2

    # Clear repository in-memory cache to force reading from database mock
    repo._by_id.clear()
    repo._by_symbol.clear()

    # Load by ID (db query)
    loaded = repo.load_snapshot("s1")
    assert loaded is not None
    assert loaded.snapshot_id == "s1"
    assert loaded.symbol == "BTCUSDT"

    # Load latest (db query)
    latest = repo.load_latest_snapshot("BTCUSDT")
    assert latest is not None
    assert latest.snapshot_id == "s2"

    # Load historical (db query)
    history = repo.get_historical_snapshots(
        "BTCUSDT", now - timedelta(seconds=10), now + timedelta(seconds=10)
    )
    assert len(history) == 2
    assert [s.snapshot_id for s in history] == ["s1", "s2"]


def test_repo_db_error_handling():
    """Verify repository raises RepositoryException when database calls fail."""

    class FailingStorageEngine:

        def write_rows(self, table, rows):
            raise RuntimeError("Database connection lost")

        def execute(self, query):
            raise RuntimeError("Database connection lost")

    repo = MarketIntelligenceRepository(storage_engine=FailingStorageEngine())
    now = datetime.now(timezone.utc)
    s1 = MarketSnapshot(snapshot_id="s1", symbol="BTCUSDT", timestamp=now, states={})

    with pytest.raises(RepositoryException, match="Failed to persist snapshot"):
        repo.save_snapshot(s1)

    # Clear in-memory caches to force storage access
    repo._by_id.clear()
    repo._by_symbol.clear()

    with pytest.raises(RepositoryException, match="Failed to load snapshot"):
        repo.load_snapshot("s1")

    with pytest.raises(RepositoryException, match="Failed to load latest snapshot"):
        repo.load_latest_snapshot("BTCUSDT")

    with pytest.raises(RepositoryException, match="Failed to load historical snapshots"):
        repo.get_historical_snapshots("BTCUSDT", now, now)

