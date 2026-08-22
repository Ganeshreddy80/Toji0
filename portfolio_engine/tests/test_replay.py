import pytest
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.state import PortfolioStateStore


def test_portfolio_replay_determinism():
    store_1 = PortfolioStateStore(initial_balance=100000.0)
    store_2 = PortfolioStateStore(initial_balance=100000.0)

    fills = [
        ("pos-1", "BTCUSD", PositionSide.LONG, 1.0, 50000.0),
        ("pos-2", "ETHUSD", PositionSide.LONG, 10.0, 3000.0),
        ("pos-1", "BTCUSD", PositionSide.SHORT, 0.5, 52000.0),  # partial reduce
        ("pos-2", "ETHUSD", PositionSide.SHORT, 10.0, 3100.0),  # complete close
    ]

    # Run fills on first store
    for f in fills:
        store_1.apply_position_fill(*f)

    # Run identical fills on second store
    for f in fills:
        store_2.apply_position_fill(*f)

    snap_1 = store_1.get_current_snapshot()
    snap_2 = store_2.get_current_snapshot()

    # The metrics must match exactly
    assert snap_1.metrics.total_realized_pnl == snap_2.metrics.total_realized_pnl
    assert snap_1.metrics.total_unrealized_pnl == snap_2.metrics.total_unrealized_pnl
    assert snap_1.metrics.gross_exposure == snap_2.metrics.gross_exposure
    assert snap_1.metrics.net_exposure == snap_2.metrics.net_exposure
    assert snap_1.metrics.portfolio_value == snap_2.metrics.portfolio_value
