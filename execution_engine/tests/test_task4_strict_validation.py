"""Unit tests for Sprint 1 Task 4: Strict Execution Validation & Fail-Closed Gating."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from execution_engine.core.enums import (
    ExecutionStatus,
    OrderSide,
    OrderState,
    OrderType,
    OrderTimeInForce,
)
from execution_engine.core.models import (
    ExecutionConfig,
    ExecutionRequest,
)
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator
from execution_engine.analysis.risk_guard import ExecutionRiskGuard
from execution_engine.analysis.execution_engine import ExecutionEngine
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore
from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.paper_broker import PaperBroker


@pytest.fixture
def execution_config() -> ExecutionConfig:
    return ExecutionConfig(
        broker_selection="paper",
        paper_broker_settings={
            "initial_balance": 100000.0,
            "max_order_age_seconds": 60.0,
        },
        min_notional_rules={"BTC": 0.001, "BTC_NOTIONAL": 10.0},
        tick_size_rules={"BTC": 0.01},
        precision_rules={"BTC": {"quantity": 4}},
    )


@pytest.fixture
def broker_router(execution_config) -> BrokerRouter:
    router = BrokerRouter()
    broker = PaperBroker(execution_config.paper_broker_settings)
    router.register_adapter("paper", broker)
    return router


@pytest.fixture
def validator(execution_config) -> ExecutionValidator:
    deduplicator = ExecutionDeduplicator()
    return ExecutionValidator(execution_config, deduplicator)


def test_task4_empty_symbol_rejection(execution_config, validator):
    """Task 4: Requests with an empty symbol must be rejected immediately."""
    req = ExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        signal_id="sig-1",
        strategy_id="strat-1",
        position_id="pos-1",
        correlation_id="corr-1",
        symbol="",
        timeframe="1h",
        quantity=1.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )
    state_store = ExecutionStateStore()
    violations = validator.validate_request(req, state_store)
    assert any("Symbol must be non-empty" in v for v in violations)


def test_task4_non_positive_quantity_rejection(execution_config, validator):
    """Task 4: Requests with quantity <= 0 must be rejected immediately."""
    req = ExecutionRequest(
        execution_id="exec-2",
        request_id="req-2",
        signal_id="sig-2",
        strategy_id="strat-2",
        position_id="pos-2",
        correlation_id="corr-2",
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=0.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )
    state_store = ExecutionStateStore()
    violations = validator.validate_request(req, state_store)
    assert any("quantity must be positive" in v.lower() for v in violations)


def test_task4_limit_order_missing_price_rejection(execution_config, validator):
    """Task 4: LIMIT orders missing a positive limit price must be rejected."""
    req = ExecutionRequest(
        execution_id="exec-3",
        request_id="req-3",
        signal_id="sig-3",
        strategy_id="strat-3",
        position_id="pos-3",
        correlation_id="corr-3",
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=1.0,
        price=None,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
    )
    state_store = ExecutionStateStore()
    violations = validator.validate_request(req, state_store)
    assert any("requires a positive limit price" in v for v in violations)


def test_task4_stop_order_missing_stop_price_rejection(execution_config, validator):
    """Task 4: STOP_MARKET orders missing a positive stop price must be rejected."""
    req = ExecutionRequest(
        execution_id="exec-4",
        request_id="req-4",
        signal_id="sig-4",
        strategy_id="strat-4",
        position_id="pos-4",
        correlation_id="corr-4",
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=1.0,
        stop_price=0.0,
        side=OrderSide.BUY,
        order_type=OrderType.STOP_MARKET,
    )
    state_store = ExecutionStateStore()
    violations = validator.validate_request(req, state_store)
    assert any("requires a positive stop price" in v for v in violations)


def test_task4_broker_offline_risk_guard_rejection(execution_config):
    """Task 4: Risk guard must reject requests when broker is offline or unreachable."""
    guard = ExecutionRiskGuard(execution_config)
    mock_adapter = MagicMock()
    mock_adapter.ping.return_value = False

    req = ExecutionRequest(
        execution_id="exec-5",
        request_id="req-5",
        signal_id="sig-5",
        strategy_id="strat-5",
        position_id="pos-5",
        correlation_id="corr-5",
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=1.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )

    violations = guard.check_request(req, mock_adapter)
    assert any("Broker connection is offline" in v for v in violations)


def test_task4_engine_submits_rejection_on_invalid_request(execution_config, broker_router, validator):
    """Task 4: ExecutionEngine.submit_execution rejects invalid request and writes rejected audit record."""
    repository = ExecutionRepository()
    state_store = ExecutionStateStore()

    engine = ExecutionEngine(
        config=execution_config,
        broker_router=broker_router,
        validator=validator,
        repository=repository,
        state_store=state_store,
    )

    invalid_req = ExecutionRequest(
        execution_id="exec-6",
        request_id="req-6",
        signal_id="sig-6",
        strategy_id="strat-6",
        position_id="pos-6",
        correlation_id="corr-6",
        symbol="BTCUSDT",
        timeframe="1h",
        quantity=-5.0,  # Invalid quantity
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
    )

    result = engine.submit_execution(invalid_req)

    assert result.status == ExecutionStatus.REJECTED
    assert len(result.orders) == 1
    assert result.orders[0].state == OrderState.REJECTED
    assert "quantity must be positive" in result.orders[0].error_message.lower()
