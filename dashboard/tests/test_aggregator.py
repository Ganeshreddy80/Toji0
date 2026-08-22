import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from dashboard.core.models import DashboardSnapshot
from dashboard.core.state import DashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.core.orchestrator import DashboardOrchestrator
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager
from dashboard.aggregator.event_aggregator import DashboardEventAggregator


class DummyEvent:
    """Mock event matching the schema containing a nested payload."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload


def test_event_aggregator_processing() -> None:
    """Test that incoming events are correctly merged into unified snapshots."""
    # 1. Setup subsystem environment
    state_store = DashboardStateStore()
    repo = DashboardRepository()
    orchestrator = DashboardOrchestrator()
    orchestrator.initialize(state_store, repo)
    
    health_monitor = HealthMonitor()
    websocket_manager = WebSocketManager()
    
    aggregator = DashboardEventAggregator(
        orchestrator=orchestrator,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
    )

    # 2. Ingest MIL Market State Update
    mil_event = DummyEvent({
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "state": {"trend": "BULLISH"}
    })
    
    aggregator.handle_market_state_updated(mil_event)

    # Check store snapshot was created
    snapshot = state_store.get_snapshot("BTC/USDT", "1h")
    assert snapshot is not None
    assert snapshot.market_state == {"trend": "BULLISH"}
    assert snapshot.pattern_state is None
    
    # 3. Ingest PAE Pattern State Update
    pae_event = DummyEvent({
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "state": {"patterns": ["double_bottom"]}
    })
    aggregator.handle_pattern_updated(pae_event)
    
    # Check snapshot was updated in-place (merging fields)
    snapshot = state_store.get_snapshot("BTC/USDT", "1h")
    assert snapshot is not None
    assert snapshot.market_state == {"trend": "BULLISH"}
    assert snapshot.pattern_state == {"patterns": ["double_bottom"]}

    # Check historical timeline log event was recorded
    history = aggregator.get_events_history()
    assert len(history) == 2
    assert history[0].subsystem == "MIL"
    assert history[1].subsystem == "PAE"

    # 4. Ingest Trading Context Update (special payload_key='context')
    tc_event = DummyEvent({
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "context": {"id": "context-abc"}
    })
    aggregator.handle_trading_context_updated(tc_event)
    
    snapshot = state_store.get_snapshot("BTC/USDT", "1h")
    assert snapshot is not None
    assert snapshot.trading_context == {"id": "context-abc"}
