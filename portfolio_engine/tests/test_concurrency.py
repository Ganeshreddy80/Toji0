import threading
import time
import pytest
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.state import PortfolioStateStore


def test_concurrent_position_updates():
    store = PortfolioStateStore(initial_balance=10000.0)

    # Parallel threads adding to LONG positions concurrently
    def run_worker(idx):
        for i in range(10):
            store.apply_position_fill(
                position_id=f"pos-{idx}-{i}",
                symbol="BTCUSD",
                side=PositionSide.LONG,
                quantity=0.1,
                price=50000.0,
            )
            store.update_market_price("BTCUSD", 51000.0)

    threads = [threading.Thread(target=run_worker, args=(i,)) for i in range(5)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    pos = store._position_store.get_position("BTCUSD")
    # 5 threads * 10 iterations * 0.1 quantity = 5.0 quantity
    assert pytest.approx(pos.quantity) == 5.0
    assert pos.current_price == 51000.0
