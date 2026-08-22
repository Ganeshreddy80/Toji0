"""Unit tests for the Confluence Snapshot Repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from data.storage.base import MockPostgresStorageEngine
from confluence.core.exceptions import RepositoryError
from confluence.core.models import (
    ConfluenceSnapshot,
    ConfluenceState,
    ConfluenceScore,
)
from confluence.core.enums import SetupGrade
from confluence.core.repository import ConfluenceRepository


def create_dummy_score() -> ConfluenceScore:
    """Create a dummy confluence score for testing."""
    return ConfluenceScore(
        overall_score=85.0,
        setup_grade=SetupGrade.B,
        trend_score=80.0,
        structure_score=80.0,
        liquidity_score=80.0,
        zone_score=80.0,
        volume_score=80.0,
        regime_score=80.0,
        session_score=80.0,
        mtf_score=80.0,
        correlation_score=80.0,
        pattern_score=80.0,
        quality_score=80.0,
        conflict_penalty=0.0,
        supporting_factors=[],
        conflicting_factors=[],
    )


def test_repository_in_memory_crud():
    """Verify in-memory CRUD operations on the repository."""
    repo = ConfluenceRepository()
    now = datetime.now(timezone.utc)

    # Load non-existent
    assert repo.load_snapshot("not-found") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None
    assert repo.get_historical_snapshots("BTCUSDT", now, now) == []

    # Try saving invalid snapshot
    with pytest.raises(RepositoryError, match="valid ID and symbol"):
        repo.save_snapshot(
            ConfluenceSnapshot(snapshot_id="", symbol="BTCUSDT", timestamp=now, states={})
        )

    # Prepare states
    state1 = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=create_dummy_score(),
        updated_at=now - timedelta(seconds=10),
    )
    state2 = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=create_dummy_score(),
        updated_at=now,
    )
    state3 = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=create_dummy_score(),
        updated_at=now + timedelta(seconds=10),
    )

    # Save snapshots
    s1 = ConfluenceSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now - timedelta(seconds=10),
        states={"1h": state1},
    )
    s2 = ConfluenceSnapshot(
        snapshot_id="s2",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state2},
    )
    s3 = ConfluenceSnapshot(
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
    repo = ConfluenceRepository(storage_engine=db)

    now = datetime.now(timezone.utc)
    state1 = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=create_dummy_score(),
        updated_at=now,
    )
    s1 = ConfluenceSnapshot(
        snapshot_id="s1",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state1},
    )

    repo.save_snapshot(s1)

    # Verify row written to DB
    assert "confluence_snapshots" in db.tables
    assert len(db.tables["confluence_snapshots"]) == 1

    # Clear repository in-memory cache to force reading from database mock
    repo._by_id.clear()
    repo._by_symbol.clear()

    # Load by ID (db query)
    loaded = repo.load_snapshot("s1")
    assert loaded is not None
    assert loaded.snapshot_id == "s1"
    assert "1h" in loaded.states
    assert loaded.states["1h"].score.overall_score == 85.0
