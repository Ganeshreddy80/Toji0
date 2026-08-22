import pytest
from datetime import datetime, timezone
from dashboard.core.exceptions import StateStoreError
from dashboard.core.models import DashboardSnapshot
from dashboard.core.state import DashboardStateStore


def test_state_store_operations() -> None:
    """Test standard update, get, list, and clear operations."""
    store = DashboardStateStore()
    assert len(store.get_all_snapshots()) == 0

    snapshot1 = DashboardSnapshot(
        snapshot_id="uuid-1",
        symbol="btc/usd",
        timeframe="1H",
        health_status={},
    )
    store.update_snapshot(snapshot1)

    # Retrieval should be case-insensitive on lookup keys
    retrieved = store.get_snapshot("BTC/USD", "1h")
    assert retrieved is not None
    assert retrieved.snapshot_id == "uuid-1"

    # All snapshots list
    all_snaps = store.get_all_snapshots()
    assert len(all_snaps) == 1
    assert all_snaps[0].snapshot_id == "uuid-1"

    # Invalid symbol/timeframe error validation
    invalid_snap = DashboardSnapshot(
        snapshot_id="uuid-2",
        symbol="",
        timeframe="1h",
        health_status={},
    )
    with pytest.raises(StateStoreError):
        store.update_snapshot(invalid_snap)

    # Clear memory
    store.clear()
    assert len(store.get_all_snapshots()) == 0
