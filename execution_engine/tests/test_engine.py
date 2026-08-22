from datetime import datetime, timezone
import pytest

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.core.enums import ExecutionStatus, OrderSide, OrderState, OrderTimeInForce, OrderType
from execution_engine.core.models import ExecutionConfig, ExecutionRequest
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator
from execution_engine.analysis.execution_engine import ExecutionEngine


def test_engine_submit_execution_success():
    config = ExecutionConfig(
        broker_selection="paper",
        min_notional_rules={"BTCUSD": 0.001, "BTCUSD_NOTIONAL": 5.0},
        precision_rules={"BTCUSD": {"quantity": 4}}
    )
    router = BrokerRouter()
    paper = PaperBroker({"initial_balance": 10000.0})
    paper.connect()
    router.register_adapter("paper", paper)
    
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    repo = ExecutionRepository()
    store = ExecutionStateStore()
    
    engine = ExecutionEngine(config, router, validator, repo, store)
    
    req = ExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        signal_id="sig-1",
        strategy_id="strat-1",
        position_id="pos-1",
        correlation_id="corr-1",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=0.1,
        price=100.0,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
    )
    
    result = engine.submit_execution(req)
    assert result.status == ExecutionStatus.EXECUTED
    assert len(result.orders) == 1
    assert result.orders[0].state == OrderState.FILLED
    assert result.metrics is not None
    assert result.metrics.commission > 0.0


def test_engine_submit_execution_validation_fail():
    config = ExecutionConfig(
        broker_selection="paper",
        min_notional_rules={"BTCUSD": 1.0, "BTCUSD_NOTIONAL": 5.0},
        precision_rules={"BTCUSD": {"quantity": 4}}
    )
    router = BrokerRouter()
    paper = PaperBroker({})
    paper.connect()
    router.register_adapter("paper", paper)
    
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    repo = ExecutionRepository()
    store = ExecutionStateStore()
    
    engine = ExecutionEngine(config, router, validator, repo, store)
    
    req = ExecutionRequest(
        execution_id="exec-2",
        request_id="req-2",
        signal_id="sig-2",
        strategy_id="strat-2",
        position_id="pos-2",
        correlation_id="corr-2",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=0.01,  # less than min 1.0 limit
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
    )
    
    result = engine.submit_execution(req)
    assert result.status == ExecutionStatus.REJECTED
    assert len(result.orders) == 1
    assert result.orders[0].state == OrderState.REJECTED
