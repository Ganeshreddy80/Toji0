"""Tests for the Position Sizing state store."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

from position_sizing.core.exceptions import StateStoreError
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import (
    PositionSizingResult,
    PositionSizingState,
    PositionSizingSnapshot,
)
from position_sizing.core.state import PositionSizingStateStore


def test_state_store_basic_operations():
    """Verify in-memory updates, fetches, and clear operations."""
    store = PositionSizingStateStore(history_limit=5)

    now = datetime.now(timezone.utc)
    res = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
    )
    state = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="1h",
        result=res,
        updated_at=now,
    )
    snap = PositionSizingSnapshot(
        snapshot_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state},
    )

    # 1. Store & Retrieve snapshot
    store.update_snapshot(snap)
    fetched = store.get_snapshot("BTCUSDT")
    assert fetched is not None
    assert fetched.snapshot_id == snap.snapshot_id

    # 2. Update timeframe state
    state2 = PositionSizingState(
        symbol="BTCUSDT",
        timeframe="4h",
        result=res,
        updated_at=now,
    )
    store.update_timeframe_state("BTCUSDT", "4h", state2)

    updated_fetched = store.get_snapshot("BTCUSDT")
    assert "4h" in updated_fetched.states
    assert "1h" in updated_fetched.states

    # 3. Retrieve history
    history = store.get_history("BTCUSDT")
    assert len(history) == 2

    # 4. Clear
    store.clear()
    assert store.get_snapshot("BTCUSDT") is None
    assert len(store.get_history("BTCUSDT")) == 0


def test_state_store_history_limits():
    """Verify that state store respects history deque limit trimming."""
    store = PositionSizingStateStore(history_limit=3)

    now = datetime.now(timezone.utc)
    res = PositionSizingResult(
        success=True,
        status=SizingStatus.APPROVED,
    )

    for i in range(5):
        snap = PositionSizingSnapshot(
            snapshot_id=f"snap-{i}",
            symbol="BTCUSDT",
            timestamp=now,
            states={},
        )
        store.update_snapshot(snap)

    history = store.get_history("BTCUSDT")
    assert len(history) == 3
    assert history[0].snapshot_id == "snap-2"
    assert history[2].snapshot_id == "snap-4"
