import pytest
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.state import PortfolioStateStore


def test_state_drawdown_and_health():
    store = PortfolioStateStore(initial_balance=100000.0)
    
    # Open LONG position
    store.apply_position_fill(
        position_id="p-1",
        symbol="BTCUSD",
        side=PositionSide.LONG,
        quantity=1.0,
        price=50000.0,
    )
    
    # Recalculate price drop to simulate drawdown
    snap = store.update_market_price("BTCUSD", 40000.0)
    # Unrealized PnL = (40000 - 50000) * 1.0 = -10000.0
    # Portfolio value = 100000 - 10000 = 90000.0
    # Peak value was 100000.0
    # Drawdown = (100000 - 90000) / 100000 = 10% (0.10)
    assert snap.metrics.portfolio_value == 90000.0
    assert snap.health.drawdown == 0.10
    assert snap.health.status == "WARNING"  # 10% > 8% threshold

    # Recalculate deep price drop
    snap_critical = store.update_market_price("BTCUSD", 30000.0)
    assert snap_critical.health.drawdown == 0.20
    assert snap_critical.health.status == "CRITICAL"  # 20% > 15% threshold

    # Reset/clear store
    store.clear()
    assert len(store._position_store.get_all_positions()) == 0
    assert store._peak_value == 100000.0
