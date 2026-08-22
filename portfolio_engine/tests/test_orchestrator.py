from datetime import datetime, timezone
import pytest
from toji_platform.core.event_bus.events import BaseEvent
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.state import PortfolioStateStore
from portfolio_engine.core.repository import PortfolioRepository
from portfolio_engine.core.orchestrator import PortfolioOrchestrator


class MockEventBus:
    def __init__(self):
        self.published = []

    def subscribe(self, event_type, handler):
        pass

    def unsubscribe(self, event_type, handler):
        pass

    def publish(self, event):
        self.published.append(event)


class MockEvent(BaseEvent):
    pass


def test_orchestrator_execution_completed():
    store = PortfolioStateStore(initial_balance=100000.0)
    repo = PortfolioRepository()
    bus = MockEventBus()
    
    orchestrator = PortfolioOrchestrator()
    orchestrator.initialize(store, repo, bus)

    # Mock ExecutionResult containing filled orders
    execution_payload = {
        "execution_id": "exec-1",
        "request_id": "req-1",
        "correlation_id": "corr-1",
        "status": "EXECUTED",
        "orders": [
            {
                "client_order_id": "o-1",
                "symbol": "BTCUSD",
                "side": "BUY",
                "price": 50000.0,
                "quantity": 1.0,
                "filled_quantity": 1.0,
                "average_fill_price": 50000.0,
                "leverage": 2.0,
                "state": "FILLED",
            }
        ],
    }

    event = MockEvent(source="test", payload=execution_payload)
    orchestrator.on_execution_completed(event)

    # Active positions check
    pos = store._position_store.get_position("BTCUSD")
    assert pos is not None
    assert pos.quantity == 1.0
    assert pos.side == PositionSide.LONG

    # Events broadcast check
    assert len(bus.published) > 0
    event_types = [e.event_type for e in bus.published]
    assert "system.position_opened" in event_types
    assert "system.portfolio_updated" in event_types
    assert "system.pnl_updated" in event_types


def test_orchestrator_update_price():
    store = PortfolioStateStore(initial_balance=100000.0)
    repo = PortfolioRepository()
    bus = MockEventBus()
    
    orchestrator = PortfolioOrchestrator()
    orchestrator.initialize(store, repo, bus)

    # Open position
    store.apply_position_fill("pos-1", "BTCUSD", PositionSide.LONG, 1.0, 50000.0)

    # Dynamic price feed
    orchestrator.update_price("BTCUSD", 55000.0)
    
    pos = store._position_store.get_position("BTCUSD")
    assert pos.current_price == 55000.0
    assert pos.unrealized_pnl == 5000.0
