import pytest
import time
from datetime import datetime, timezone
import uuid

from toji_platform.boot import boot_kernel
from toji_platform.core.event_bus.events import (
    MarketDataReceived,
    MarketIntelligenceCompleted,
    PriceActionCompleted,
    ConfluenceCompleted,
    StrategyGenerated,
    RiskChecked,
    DashboardUpdated
)
from trading_context.core.events import TradingContextUpdated
from position_sizing.core.events import PositionSizeCalculated
from execution_engine.core.events import ExecutionRequested, ExecutionCompleted
from portfolio_engine.core.events import PortfolioUpdated
from data.schemas.market_data import OHLCV
from toji_platform.core.event_bus.bus import InMemoryEventBus
from execution_engine.core.models import ExecutionResult, Order
from execution_engine.core.enums import OrderState, ExecutionStatus
from portfolio_engine.core.state import PortfolioStateStore
from dashboard.core.interfaces import IDashboardStateStore


def test_end_to_end_pipeline_integration():
    """Verify that all plugins are subscribed correctly and events flow sequentially."""
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})
    bus = kernel.event_bus

    # Keep track of received events
    received_events = {}

    def get_tracker(etype):
        def tracker(event):
            received_events[etype] = event
        return tracker

    event_types = [
        "system.market_data_received",
        "system.market_intelligence_completed",
        "system.price_action_completed",
        "system.confluence_completed",
        "system.strategy_generated",
        "system.trading_context_updated",
        "system.risk_checked",
        "system.position_size_calculated",
        "system.execution_requested",
        "system.execution_completed",
        "system.portfolio_updated",
        "system.dashboard_updated",
    ]

    for etype in event_types:
        bus.subscribe(etype, get_tracker(etype))

    # Test Symbol & Timeframe
    symbol = "BTC/USDT"
    timeframe = "1m"

    # Connect the paper broker manually to ensure it's online for the test
    from execution_engine.core.interfaces import IExecutionEngine
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    # Clear portfolio and paper broker state from previous runs
    paper_broker._positions.clear()
    paper_broker._open_orders.clear()
    paper_broker._fills_log.clear()
    paper_broker._balance = {"USD": 100000.0}

    portfolio_store = kernel.container.resolve(PortfolioStateStore)
    portfolio_store.clear()

    # 1. Trigger pipeline entry point: MarketDataReceived
    candle = OHLCV(
        symbol=symbol,
        interval=timeframe,
        open=50000.0,
        high=50500.0,
        low=49900.0,
        close=50200.0,
        volume=1.5,
        timestamp=datetime.now(timezone.utc),
    )
    market_data_event = MarketDataReceived(
        source="test_gateway",
        payload={
            "symbol": symbol,
            "candle": candle.model_dump(),
        }
    )
    bus.publish(market_data_event)

    # Assert event propagation through all analysis steps automatically
    assert "system.market_data_received" in received_events
    assert "system.market_intelligence_completed" in received_events
    assert "system.price_action_completed" in received_events
    assert "system.confluence_completed" in received_events
    assert "system.strategy_generated" in received_events
    assert "system.trading_context_updated" in received_events
    assert "system.risk_checked" in received_events

    # Clear portfolio and paper broker state from the automatic execution before manually triggering it
    paper_broker._positions.clear()
    paper_broker._open_orders.clear()
    paper_broker._fills_log.clear()
    paper_broker._balance = {"USD": 100000.0}
    portfolio_store.clear()
    received_events.clear()

    # Now manually publish PositionSizeCalculated to verify the execution and portfolio/dashboard sync
    sizing_state_data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "result": {
            "success": True,
            "status": "APPROVED",
            "position_size": {
                "symbol": symbol,
                "timeframe": timeframe,
                "quantity": 20.0,
                "lots": 20.0,
                "leverage": 1.0,
                "margin_required": 10.0,
                "account_risk_percent": 0.01,
                "capital_used": 25000.0,
                "stop_distance": 500.0,
                "take_profit_distance": 1000.0,
                "sizing_method": "fixed_fractional",
                "confidence": 1.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "reasons": ["Approved for test"],
            "violations": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    size_calculated_event = PositionSizeCalculated(
        source="test_sizing",
        payload={
            "symbol": symbol,
            "timeframe": timeframe,
            "state": sizing_state_data
        }
    )
    bus.publish(size_calculated_event)

    # Assert Execution, Portfolio, and Dashboard are triggered automatically
    assert "system.position_size_calculated" in received_events
    assert "system.execution_requested" in received_events
    assert "system.execution_completed" in received_events
    assert "system.portfolio_updated" in received_events
    assert "system.dashboard_updated" in received_events

    # Verify Portfolio State Store actually registered the position automatically
    portfolio_store = kernel.container.resolve(PortfolioStateStore)
    snap = portfolio_store.get_current_snapshot()
    assert symbol in snap.positions
    assert snap.positions[symbol].quantity == 20.0

    # Verify Dashboard State Store contains the snapshot data
    dashboard_store = kernel.container.resolve(IDashboardStateStore)
    dash_snap = dashboard_store.get_snapshot(symbol, "all")
    assert dash_snap is not None
    assert dash_snap.portfolio_state is not None

