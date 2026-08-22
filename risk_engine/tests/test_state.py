"""Unit tests for the Risk Engine State Store."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from risk_engine.core.exceptions import StateStoreError
from risk_engine.core.enums import RiskDecision
from risk_engine.core.models import (
    RiskState,
    RiskAssessment,
    RiskSnapshot,
)
from risk_engine.core.state import RiskStateStore


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


def test_state_store_basic_operations(dummy_snapshot):
    """Verify storing, retrieving, updating timeframe, and clear operations."""
    store = RiskStateStore(history_limit=5)

    # Load non-existent
    assert store.get_snapshot("BTCUSDT") is None

    # Invalid symbol raises StateStoreError
    with pytest.raises(StateStoreError):
        store.update_snapshot(
            RiskSnapshot(snapshot_id="snap-1", symbol="", timestamp=datetime.now(timezone.utc))
        )

    # Save
    store.update_snapshot(dummy_snapshot)
    assert store.get_snapshot("BTCUSDT") == dummy_snapshot

    # Update timeframe state
    dt = datetime.now(timezone.utc)
    new_state = RiskState(
        symbol="BTCUSDT",
        timeframe="15m",
        assessment=RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW),
        updated_at=dt,
    )
    updated_snap = store.update_timeframe_state("BTCUSDT", "15m", new_state)

    assert "15m" in updated_snap.states
    assert updated_snap.states["15m"] == new_state
    assert updated_snap.timestamp == dt

    # Clear
    store.clear()
    assert store.get_snapshot("BTCUSDT") is None
    assert store.get_history("BTCUSDT") == []


def test_state_store_history_limits(dummy_snapshot):
    """Verify history limit constraints."""
    store = RiskStateStore(history_limit=3)

    for i in range(5):
        snap = dummy_snapshot.model_copy(update={"snapshot_id": f"snap-{i}"})
        store.update_snapshot(snap)

    history = store.get_history("BTCUSDT")
    assert len(history) == 3
    assert history[0].snapshot_id == "snap-2"
    assert history[1].snapshot_id == "snap-3"
    assert history[2].snapshot_id == "snap-4"
