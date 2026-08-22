"""Unit tests for the Risk Engine Repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from data.storage.base import MockPostgresStorageEngine
from risk_engine.core.exceptions import RepositoryError
from risk_engine.core.enums import RiskDecision
from risk_engine.core.models import (
    RiskState,
    RiskAssessment,
    RiskSnapshot,
)
from risk_engine.core.repository import RiskRepository


@pytest.fixture
def dummy_snapshot() -> RiskSnapshot:
    dt = datetime.now(timezone.utc)
    assessment = RiskAssessment(overall_score=100.0, decision=RiskDecision.ALLOW)
    state = RiskState(symbol="BTCUSDT", timeframe="1h", assessment=assessment, updated_at=dt)
    return RiskSnapshot(
        snapshot_id="snap-123",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": state},
    )


def test_repository_in_memory_crud(dummy_snapshot):
    """Verify standard CRUD operations without database storage."""
    repo = RiskRepository()
    now = datetime.now(timezone.utc)

    # Empty checks
    assert repo.load_snapshot("not-found") is None
    assert repo.load_latest_snapshot("BTCUSDT") is None
    assert repo.get_historical_snapshots("BTCUSDT", now, now) == []

    # Invalid check
    with pytest.raises(RepositoryError):
        repo.save_snapshot(
            RiskSnapshot(snapshot_id="", symbol="BTCUSDT", timestamp=now, states={})
        )

    # Save snapshots
    s1 = dummy_snapshot.model_copy(update={"snapshot_id": "s1", "timestamp": now - timedelta(seconds=10)})
    s2 = dummy_snapshot.model_copy(update={"snapshot_id": "s2", "timestamp": now})
    s3 = dummy_snapshot.model_copy(update={"snapshot_id": "s3", "timestamp": now + timedelta(seconds=10)})

    repo.save_snapshot(s2)
    repo.save_snapshot(s1)
    repo.save_snapshot(s3)

    assert repo.load_snapshot("s1") == s1
    assert repo.load_snapshot("s2") == s2
    assert repo.load_latest_snapshot("BTCUSDT") == s3

    # Historical retrieval
    history = repo.get_historical_snapshots("BTCUSDT", now - timedelta(seconds=5), now + timedelta(seconds=15))
    assert len(history) == 2
    assert [s.snapshot_id for s in history] == ["s2", "s3"]


def test_repository_with_postgres_storage(dummy_snapshot):
    """Verify repository persistence using MockPostgresStorageEngine."""
    db = MockPostgresStorageEngine()
    db.connect()
    repo = RiskRepository(storage_engine=db)

    now = datetime.now(timezone.utc)
    s1 = dummy_snapshot.model_copy(update={"snapshot_id": "s1", "timestamp": now})
    repo.save_snapshot(s1)

    # Verify table write
    assert "risk_states" in db.tables
    assert len(db.tables["risk_states"]) == 1

    # Clear repository local cache to force db fetch
    repo._by_id.clear()
    repo._by_symbol.clear()

    # Load by ID
    loaded = repo.load_snapshot("s1")
    assert loaded is not None
    assert loaded.snapshot_id == "s1"
    assert "1h" in loaded.states
    assert loaded.states["1h"].symbol == "BTCUSDT"
