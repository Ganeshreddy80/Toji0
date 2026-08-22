from datetime import datetime, timezone
import pytest
from execution_engine.core.enums import OrderSide, OrderType
from execution_engine.core.models import ExecutionConfig, ExecutionRequest
from execution_engine.analysis.risk_guard import ExecutionRiskGuard
from execution_engine.brokers.paper_broker import PaperBroker


def test_risk_guard_validation():
    config = ExecutionConfig(
        timeouts_ms={"max_margin_per_order": 1000}
    )
    guard = ExecutionRiskGuard(config)
    
    req = ExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        signal_id="sig-1",
        strategy_id="strat-1",
        position_id="pos-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=1.0,
        price=100.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        margin_required=1500.0,  # Exceeds max margin of 1000
    )
    
    broker = PaperBroker({"initial_balance": 10000.0})
    broker.connect()
    
    # Check margin violation
    violations = guard.check_request(req, broker)
    assert len(violations) == 1
    assert "margin required" in violations[0].lower()

    # Check market halted violation
    guard.set_market_halted("BTCUSD", True)
    violations_2 = guard.check_request(req, broker)
    assert len(violations_2) == 2
    assert any("halted" in v.lower() for v in violations_2)

    # Check symbol disabled violation
    guard.disable_symbol("BTCUSD", True)
    violations_3 = guard.check_request(req, broker)
    assert len(violations_3) == 3
    assert any("disabled" in v.lower() for v in violations_3)

    # Check locked position violation
    guard.lock_position("pos-1", True)
    violations_4 = guard.check_request(req, broker)
    assert len(violations_4) == 4
    assert any("locked" in v.lower() for v in violations_4)
