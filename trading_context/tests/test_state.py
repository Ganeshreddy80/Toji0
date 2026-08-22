"""Unit tests for the Trading Context State Store."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from trading_context.core.exceptions import StateStoreError
from trading_context.core.models import (
    TradingContext,
    TradingContextSnapshot,
)
from trading_context.core.state import TradingContextStateStore


@pytest.fixture
def dummy_context() -> TradingContext:
    """Create a dummy TradingContext for state store testing."""
    dt = datetime.now(timezone.utc)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=dt),
        strategy_state=StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt),
        generated_at=dt,
    )


def test_state_store_basic_operations(dummy_context):
    """Verify storing, retrieving, and clear operations."""
    store = TradingContextStateStore(history_limit=5)
    
    # Get non-existent
    assert store.get_snapshot("BTCUSDT") is None

    # Try updating snapshot when symbol is empty
    with pytest.raises(StateStoreError):
        store.update_snapshot(
            TradingContextSnapshot(snapshot_id="snap-1", symbol="", timestamp=datetime.now(timezone.utc))
        )

    # Store first snapshot
    now = datetime.now(timezone.utc)
    s1 = TradingContextSnapshot(
        snapshot_id="snap-1",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": dummy_context},
    )
    store.update_snapshot(s1)
    
    loaded = store.get_snapshot("BTCUSDT")
    assert loaded == s1

    # Update timeframe state
    dt2 = datetime.now(timezone.utc)
    c2 = dummy_context.model_copy(update={"timeframe": "15m", "generated_at": dt2})
    
    updated_snap = store.update_timeframe_state("BTCUSDT", "15m", c2)
    assert "15m" in updated_snap.states
    assert updated_snap.states["15m"] == c2
    assert updated_snap.timestamp == dt2

    # Clear state store
    store.clear()
    assert store.get_snapshot("BTCUSDT") is None
    assert store.get_history("BTCUSDT") == []


def test_state_store_history_limits(dummy_context):
    """Verify store limits deque history."""
    store = TradingContextStateStore(history_limit=3)
    
    for i in range(5):
        snap = TradingContextSnapshot(
            snapshot_id=f"snap-{i}",
            symbol="BTCUSDT",
            timestamp=datetime.now(timezone.utc),
            states={"1h": dummy_context},
        )
        store.update_snapshot(snap)

    history = store.get_history("BTCUSDT")
    assert len(history) == 3
    # Check that latest snapshots are in history
    assert history[0].snapshot_id == "snap-2"
    assert history[1].snapshot_id == "snap-3"
    assert history[2].snapshot_id == "snap-4"
