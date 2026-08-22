import threading
from datetime import datetime, timezone

from execution_engine.core.enums import OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import ExecutionRequest, ExecutionState, Order
from execution_engine.core.state import ExecutionStateStore, OrderBook


def test_order_book_operations():
    book = OrderBook()
    order = Order(
        client_order_id="ord-1",
        execution_id="exec-1",
        request_id="req-1",
        signal_id="sig-1",
        strategy_id="strat-1",
        position_id="pos-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        time_in_force=OrderTimeInForce.GTC,
        state=OrderState.CREATED,
    )
    
    book.add_or_update_order(order)
    assert book.get_order("ord-1") is not None
    assert len(book.get_working_orders()) == 0  # CREATED is not a working state in our list
    
    # Update to SUBMITTED (working)
    submitted_order = order.model_copy(update={"state": OrderState.SUBMITTED})
    book.add_or_update_order(submitted_order)
    assert len(book.get_working_orders()) == 1
    assert len(book.get_open_orders()) == 1


def test_execution_state_store_thread_safety():
    store = ExecutionStateStore()
    
    def worker(idx: int):
        req = ExecutionRequest(
            execution_id=f"exec-{idx}",
            request_id=f"req-{idx}",
            signal_id="sig-1",
            strategy_id="strat-1",
            position_id="pos-1",
            correlation_id="corr-1",
            symbol="BTCUSD",
            timeframe="1h",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        state = ExecutionState(
            symbol="BTCUSD",
            timeframe="1h",
            request=req,
            orders=[],
            updated_at=datetime.now(timezone.utc),
        )
        store.update_execution_state(state)

    threads = []
    for i in range(50):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(store.get_all_execution_states()) == 50
