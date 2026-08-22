import pytest
from datetime import datetime, timezone
from portfolio_engine.core.enums import PositionSide, PositionState
from portfolio_engine.core.state import PortfolioStateStore


def test_position_lifecycle_long():
    store = PortfolioStateStore(initial_balance=10000.0)

    # 1. Open Position
    snap, opened, closed = store.apply_position_fill(
        position_id="p-1",
        symbol="BTCUSD",
        side=PositionSide.LONG,
        quantity=1.0,
        price=100.0,
        leverage=2.0,
        fees=1.0,
    )
    assert opened is not None
    assert closed is None
    assert snap.metrics.portfolio_value == 10000.0
    assert store._position_store.get_position("BTCUSD").quantity == 1.0

    # 2. Add to Position
    snap_add, opened_add, closed_add = store.apply_position_fill(
        position_id="p-1",
        symbol="BTCUSD",
        side=PositionSide.LONG,
        quantity=1.0,
        price=110.0,
        leverage=2.0,
        fees=1.0,
    )
    assert opened_add is None
    assert closed_add is None
    pos = store._position_store.get_position("BTCUSD")
    assert pos.quantity == 2.0
    assert pos.average_entry == 105.0  # (1*100 + 1*110) / 2

    # 3. Partial Reduction
    snap_red, opened_red, closed_red = store.apply_position_fill(
        position_id="p-1",
        symbol="BTCUSD",
        side=PositionSide.SHORT,  # opposite side reduces
        quantity=1.0,
        price=120.0,
        fees=1.0,
    )
    assert opened_red is None
    assert closed_red is None
    pos_red = store._position_store.get_position("BTCUSD")
    assert pos_red.quantity == 1.0
    # Realized pnl on reduction: (120 - 105) * 1.0 - 1.0 = 14.0
    assert pos_red.realized_pnl == 14.0

    # 4. Final Close
    snap_close, opened_close, closed_close = store.apply_position_fill(
        position_id="p-1",
        symbol="BTCUSD",
        side=PositionSide.SHORT,
        quantity=1.0,
        price=125.0,
        fees=1.0,
    )
    assert opened_close is None
    assert closed_close is not None
    assert closed_close.average_exit == 125.0
    # Realized pnl on final close: (125 - 105) * 1.0 - 1.0 = 19.0
    # Total realized = 14.0 (from previous) + 19.0 = 33.0.
    # Total fees accumulated = 1.0 (open) + 1.0 (add) + 1.0 (reduce) + 1.0 (close) = 4.0 (net pnl 29.0)
    assert closed_close.realized_pnl == 33.0
    assert store._position_store.get_position("BTCUSD") is None
