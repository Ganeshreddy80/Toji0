from datetime import datetime, timezone
from typing import Any, List

from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.core.event_bus.interfaces import IEventBus
from position_sizing.core.events import PositionSizeCalculated
from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.core.enums import ExecutionStatus
from execution_engine.core.models import ExecutionConfig
from execution_engine.core.orchestrator import ExecutionOrchestrator
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator
from execution_engine.analysis.execution_engine import ExecutionEngine


class MockEventBus(IEventBus):
    """Mock event bus tracking published events for testing assertions."""

    def __init__(self) -> None:
        self.published_events: List[BaseEvent] = []

    def publish(self, event: Any) -> None:
        self.published_events.append(event)

    def subscribe(self, event_type: str, handler: Any) -> None:
        pass

    def unsubscribe(self, event_type: str, handler: Any) -> None:
        pass

    def has_subscribers(self, event_type: str) -> bool:
        return True

    def clear(self) -> None:
        self.published_events.clear()


def test_orchestrator_on_position_size_calculated():
    bus = MockEventBus()
    store = ExecutionStateStore()
    repo = ExecutionRepository()
    
    config = ExecutionConfig(
        broker_selection="paper",
        min_notional_rules={"BTCUSD": 0.001, "BTCUSD_NOTIONAL": 5.0},
        precision_rules={"BTCUSD": {"quantity": 4}}
    )
    router = BrokerRouter()
    paper = PaperBroker({"initial_balance": 100000.0})
    paper.connect()
    router.register_adapter("paper", paper)
    
    dedup = ExecutionDeduplicator()
    validator = ExecutionValidator(config, dedup)
    engine = ExecutionEngine(config, router, validator, repo, store)
    
    orchestrator = ExecutionOrchestrator()
    orchestrator.initialize(store, repo, engine, bus)
    
    # Construct a Mock PositionSizeCalculated event payload
    # NOTE: side must be explicit — the P1-A fix removed the silent BUY fallback.
    event_payload = {
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "side": "BUY",
        "request_id": "sizing-req-1",
        "correlation_id": "sizing-corr-1",
        "state": {
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "result": {
                "success": True,
                "status": "APPROVED",
                "position_size": {
                    "symbol": "BTCUSD",
                    "timeframe": "1h",
                    "quantity": 10.0,
                    "lots": 10.0,
                    "leverage": 1.0,
                    "margin_required": 10.0,
                    "account_risk_percent": 0.01,
                    "capital_used": 50.0,
                    "stop_distance": 5.0,
                    "take_profit_distance": 15.0,
                    "sizing_method": "FIXED_RISK",
                    "confidence": 1.0,
                },
                "reasons": [],
                "violations": [],
            },
        },
    }
    
    event = PositionSizeCalculated(
        payload=event_payload,
    )
    
    result = orchestrator.on_position_size_calculated(event)
    assert result is None
    
    # Assert that execution_requested was published
    event_types = [e.event_type for e in bus.published_events]
    assert "system.execution_requested" in event_types

    # Find the requested event
    req_event = next(e for e in bus.published_events if e.event_type == "system.execution_requested")
    
    # Simulate risk engine approval
    from execution_engine.core.events import ExecutionApproved
    approved_event = ExecutionApproved(
        source="risk_engine",
        payload=req_event.payload,
    )
    
    # Process approved execution
    exec_result = orchestrator.on_execution_approved(approved_event)
    assert exec_result is not None
    assert exec_result.status == ExecutionStatus.EXECUTED
    
    # Assert execution lifecycle events were published
    final_event_types = [e.event_type for e in bus.published_events]
    assert "system.execution_validated" in final_event_types
    assert "system.execution_submitted" in final_event_types
    assert "system.execution_filled" in final_event_types
    assert "system.execution_completed" in final_event_types
