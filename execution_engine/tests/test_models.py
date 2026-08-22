from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from execution_engine.core.enums import OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import ExecutionConfig, ExecutionRequest, Order


def test_execution_config_defaults():
    config = ExecutionConfig()
    assert config.broker_selection == "paper"
    assert config.heartbeat_interval_seconds == 30
    assert config.reconnect_interval_seconds == 5


def test_execution_request_validation():
    req = ExecutionRequest(
        execution_id="exec-123",
        request_id="req-123",
        signal_id="sig-123",
        strategy_id="strat-123",
        position_id="pos-123",
        correlation_id="corr-123",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=1.5,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.GTC,
    )
    assert req.execution_id == "exec-123"
    assert req.quantity == 1.5
    assert req.side == OrderSide.BUY

    # Validate immutable / frozen model
    with pytest.raises(ValidationError):
        # Setting attributes directly should raise ValidationError or AttributeError depending on config
        # Pydantic V2 frozen models raise ValidationError/AttributeError on mutation
        req.quantity = 2.0  # type: ignore


def test_order_creation_and_defaults():
    order = Order(
        client_order_id="client-ord-1",
        execution_id="exec-123",
        request_id="req-123",
        signal_id="sig-123",
        strategy_id="strat-123",
        position_id="pos-123",
        correlation_id="corr-123",
        symbol="ETHUSD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=10.0,
        price=1800.0,
        time_in_force=OrderTimeInForce.IOC,
        state=OrderState.CREATED,
    )
    assert order.state == OrderState.CREATED
    assert order.filled_quantity == 0.0
    assert order.average_fill_price is None
