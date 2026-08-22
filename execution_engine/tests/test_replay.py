from datetime import datetime, timezone
import pytest

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.core.enums import ExecutionStatus, OrderSide, OrderState, OrderType
from execution_engine.core.models import ExecutionConfig, ExecutionRequest
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator
from execution_engine.analysis.execution_engine import ExecutionEngine
from execution_engine.analysis.replay import ExecutionReplayEngine, ReplayJournal


def test_replay_idempotency_determinism():
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
        execution_id="exec-replay",
        request_id="req-replay",
        signal_id="sig-replay",
        strategy_id="strat-replay",
        position_id="pos-replay",
        correlation_id="corr-replay",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=0.1,
        price=100.0,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
    )
    
    # First execution should succeed
    result_1 = engine.submit_execution(req)
    assert result_1.status == ExecutionStatus.EXECUTED
    
    # Replayed identical request_id should be blocked and marked REJECTED (deduplicated)
    result_2 = engine.submit_execution(req)
    assert result_2.status == ExecutionStatus.REJECTED
    assert "Duplicate execution" in result_2.orders[0].error_message


def test_execution_replay_engine_flow():
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
    replay_engine = ExecutionReplayEngine(engine)
    
    req = ExecutionRequest(
        execution_id="exec-rep-e",
        request_id="req-rep-e",
        signal_id="sig-rep-e",
        strategy_id="strat-rep-e",
        position_id="pos-rep-e",
        correlation_id="corr-rep-e",
        symbol="BTCUSD",
        timeframe="1h",
        quantity=0.1,
        price=100.0,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
    )
    
    # Form replay journal
    journal = ReplayJournal(
        requests=[req],
        expected_order_states={"ord-exec-rep-e": OrderState.FILLED}
    )
    
    result = replay_engine.run_replay(journal)
    assert result.success is True
    assert result.replayed_orders_count == 1
    assert len(result.mismatches) == 0
