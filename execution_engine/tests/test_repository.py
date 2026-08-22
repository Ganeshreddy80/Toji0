from datetime import datetime, timezone

from execution_engine.core.enums import OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import ExecutionRequest, Order
from execution_engine.core.repository import ExecutionRepository


def test_repository_save_and_load():
    repo = ExecutionRepository()
    
    req = ExecutionRequest(
        execution_id="exec-123",
        request_id="req-123",
        signal_id="sig-123",
        strategy_id="strat-123",
        position_id="pos-123",
        correlation_id="corr-123",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=0.5,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )
    repo.save_request(req)
    
    order = Order(
        client_order_id="ord-123",
        execution_id="exec-123",
        request_id="req-123",
        signal_id="sig-123",
        strategy_id="strat-123",
        position_id="pos-123",
        correlation_id="corr-123",
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.5,
        time_in_force=OrderTimeInForce.GTC,
        state=OrderState.CREATED,
    )
    repo.save_order(order)
    
    loaded_order = repo.load_order("ord-123")
    assert loaded_order is not None
    assert loaded_order.client_order_id == "ord-123"
    assert loaded_order.quantity == 0.5
