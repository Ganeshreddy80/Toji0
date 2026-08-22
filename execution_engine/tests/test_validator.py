from datetime import datetime, timezone, timedelta
import pytest

from execution_engine.core.enums import OrderSide, OrderType
from execution_engine.core.models import ExecutionConfig, ExecutionRequest
from execution_engine.core.state import ExecutionStateStore
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator


def test_validator_deduplication():
    config = ExecutionConfig()
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    store = ExecutionStateStore()

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
    )

    violations = validator.validate_request(req, store)
    assert len(violations) == 0

    # Mark as processed
    dedup.register_request("req-1")

    # Second check should return a violation
    violations_2 = validator.validate_request(req, store)
    assert len(violations_2) == 1
    assert "Duplicate execution" in violations_2[0]


def test_validator_stale_signal():
    config = ExecutionConfig(
        paper_broker_settings={"max_order_age_seconds": 10.0}
    )
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    store = ExecutionStateStore()

    # Create request 15 seconds in the past
    past_time = datetime.now(timezone.utc) - timedelta(seconds=15)
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
        timestamp=past_time,
    )

    violations = validator.validate_request(req, store)
    assert len(violations) == 1
    assert "Stale signal" in violations[0]


def test_validator_precision_violation():
    config = ExecutionConfig(
        precision_rules={"BTCUSD": {"quantity": 2}},
        min_notional_rules={"BTCUSD": 0.01}
    )
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    store = ExecutionStateStore()

    req = ExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        signal_id="sig-1",
        strategy_id="strat-1",
        position_id="pos-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=1.0005,  # Exceeds precision of 2
        price=100.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )

    violations = validator.validate_request(req, store)
    assert len(violations) == 1
    assert "Quantity precision" in violations[0]
