from datetime import datetime, timezone
import pytest
from execution_engine.core.enums import OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import Order, OrderFill
from execution_engine.core.oms import OrderManager, FillManager, BrokerManager, ExecutionManager
from execution_engine.brokers.paper_broker import PaperBroker


def test_order_manager_lifecycle():
    mgr = OrderManager()
    order = Order(
        client_order_id="c-1",
        execution_id="e-1",
        request_id="r-1",
        signal_id="s-1",
        strategy_id="st-1",
        position_id="p-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=100.0,
        time_in_force=OrderTimeInForce.GTC,
        state=OrderState.CREATED,
    )

    mgr.add_order(order)
    assert len(mgr.get_all_orders()) == 1
    assert mgr.get_order("c-1") == order
    assert len(mgr.get_open_orders()) == 1

    # Update state to FILLED
    filled_order = order.model_copy(update={"state": OrderState.FILLED})
    mgr.update_order(filled_order)
    assert len(mgr.get_open_orders()) == 0
    assert len(mgr.get_completed_orders()) == 1


def test_fill_manager_aggregation():
    mgr = FillManager()
    fill = OrderFill(
        fill_id="f-1",
        order_id="o-1",
        client_order_id="c-1",
        execution_id="e-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        quantity=0.5,
        price=100.0,
        commission=1.5,
        fee_currency="USD",
    )

    mgr.add_fill(fill)
    assert len(mgr.get_all_fills()) == 1
    assert mgr.get_total_commission("USD") == 1.5
    assert len(mgr.get_fills_for_order("c-1")) == 1


def test_broker_manager_registration():
    mgr = BrokerManager()
    broker = PaperBroker({"initial_balance": 1000.0})
    mgr.register_broker("paper_broker", broker)
    
    assert mgr.get_broker("paper_broker") == broker
    assert mgr.get_broker("PAPER_BROKER") == broker  # check case-insensitivity
    assert len(mgr.get_all_brokers()) == 1
