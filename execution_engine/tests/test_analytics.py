from datetime import datetime, timezone, timedelta
import pytest
from execution_engine.core.enums import OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import Order, ExecutionMetrics
from execution_engine.analysis.analytics import ExecutionAnalyticsCalculator


def test_analytics_rolling_calculations():
    calc = ExecutionAnalyticsCalculator()
    
    order_1 = Order(
        client_order_id="o-1",
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
        state=OrderState.FILLED,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=2),
    )
    
    order_2 = Order(
        client_order_id="o-2",
        execution_id="e-2",
        request_id="r-2",
        signal_id="s-2",
        strategy_id="st-2",
        position_id="p-2",
        correlation_id="corr-2",
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=100.0,
        time_in_force=OrderTimeInForce.GTC,
        state=OrderState.REJECTED,
        created_at=datetime.now(timezone.utc),
    )

    metrics_1 = ExecutionMetrics(
        execution_id="e-1",
        correlation_id="corr-1",
        queue_time_ms=5.0,
        validation_time_ms=2.0,
        broker_latency_ms=25.0,
        slippage=0.01,
        commission=2.5,
    )
    
    metrics_2 = ExecutionMetrics(
        execution_id="e-2",
        correlation_id="corr-2",
        queue_time_ms=10.0,
        validation_time_ms=3.0,
        broker_latency_ms=0.0,
        slippage=0.0,
        commission=0.0,
    )

    calc.record_order(order_1)
    calc.record_order(order_2)
    calc.record_metrics(metrics_1)
    calc.record_metrics(metrics_2)
    calc.update_queue_stats(2)
    calc.update_queue_stats(1)

    summary = calc.get_summary()
    assert summary["success_rate"] == 0.5
    assert summary["fill_rate"] == 0.5
    assert summary["average_latency_ms"] == 12.5
    assert summary["average_commission"] == 1.25
    assert summary["peak_queue_size"] == 2
    assert summary["queue_depth"] == 1
