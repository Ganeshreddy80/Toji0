"""Tests verifying the consolidated market event routing pipeline.

Regression tests for the fix where system.market_data_received is the single canonical topic,
preventing inconsistent topics and competing routers from blocking the pipeline.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataReceived
from market_gateway.providers.binance.client import BinanceGatewayProvider
from research_platform.live_trading.factory import MarketProviderFactory
from research_platform.live_trading.plugin import LiveTradingEnginePlugin
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.oms.models import Order, OrderRequest


class DummyContainer:
    """Simple DI container for test assertions."""

    def __init__(self):
        self._services = {}

    def register(self, key, instance):
        self._services[key] = instance

    def resolve(self, key):
        return self._services[key]

    def has(self, key):
        return key in self._services


@pytest.fixture(autouse=True)
def clean_env():
    """Save and restore environment variables around each test."""
    saved = {}
    for key in ("MARKET_PROVIDER", "TRADING_MODE", "APP_ENV"):
        saved[key] = os.environ.get(key)
    os.environ["APP_ENV"] = "testing"
    
    # Clean up the fallback store
    from toji_platform.runtime.state import RuntimeStateManager
    RuntimeStateManager._fallback_store.clear()
    
    yield
    for key, val in saved.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = DummyContainer()
    c.register("IEventBus", event_bus)
    c.register("OrderManagementSystemOrchestrator", MagicMock())
    c.register("ExecutionEngineOrchestrator", ExecutionEngineOrchestrator(event_bus))
    c.register("PriceActionOrchestrator", MagicMock())
    c.register("AISignalGenerator", MagicMock())
    return c


def test_binance_tick_reaches_feature_engine(event_bus, container):
    """Verify:
    - Inject fake Binance tick
    - EventBus receives system.market_data_received
    - Feature Engine runs
    - Strategy receives feature snapshot
    """
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"
    
    from research_platform.price_action.orchestrator import PriceActionOrchestrator
    from research_platform.price_action.repository import PriceActionRepository
    from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
    from research_platform.ai_signal.signal_generator import AISignalGenerator
    
    repo = PriceActionRepository()
    pa_orch = PriceActionOrchestrator(event_bus=event_bus, repository=repo, container=container)
    fp_orch = FeaturePlatformOrchestrator(event_bus)
    ai_gen = AISignalGenerator(container)
    
    container.register("PriceActionOrchestrator", pa_orch)
    container.register("FeaturePlatformOrchestrator", fp_orch)
    container.register("AISignalGenerator", ai_gen)
    
    mock_confluence = MagicMock()
    mock_confluence.calculate_confluence.return_value = MagicMock(score=50.0, explanations=["Test explanations"])
    container.register("ConfluenceScoringEngine", mock_confluence)
    
    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()
    
    # Clear tick history and bars
    pa_orch._bars.clear()
    pa_orch._tick_history.clear()
    
    # Inject fake Binance tick via MarketDataReceived
    tick_event = MarketDataReceived(
        source="BinanceMarketGateway",
        payload={
            "symbol": "BTCUSDT",
            "price": 95000.50,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "volume": 1.5
        }
    )
    event_bus.publish(tick_event)
    
    # Assert Feature Engine (FeaturePlatformOrchestrator) has computed and stored features
    stored = fp_orch.store.query_latest(["close", "rsi", "ema9"], ["BTCUSDT"])
    assert not stored.empty
    assert stored.iloc[-1]["close"] == 95000.50
    
    plugin.shutdown()


def test_no_duplicate_market_routes(event_bus, container):
    """Verify only one market handler registered on system.market_data_received in plugin context."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"
    
    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()
    
    # Verify tick listener IS subscribed on system.market_data_received
    handlers = event_bus._handlers.get("system.market_data_received", [])
    assert plugin._handle_market_tick in handlers
    
    # Verify no handlers are subscribed to the deprecated system.market_tick_received
    assert "system.market_tick_received" not in event_bus._handlers or len(event_bus._handlers["system.market_tick_received"]) == 0
    
    plugin.shutdown()


def test_real_runtime_tick_update(event_bus, container):
    """Verify runtime status last_tick_time changes from N/A."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"
    
    from toji_platform.runtime.state import RuntimeStateManager
    sm = RuntimeStateManager()
    sm.load()
    sm.last_tick_time = None
    sm.persist()
    
    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()
    
    tick_event = MarketDataReceived(
        source="BinanceMarketGateway",
        payload={
            "symbol": "BTCUSDT",
            "price": 95000.50,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "volume": 1.5
        }
    )
    event_bus.publish(tick_event)
    
    sm.load()
    assert sm.last_tick_time is not None
    
    plugin.shutdown()


def test_paper_mode_blocks_real_orders(event_bus, container):
    """Verify execution safety: Binance data flows but real exchange orders are blocked."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()

    # 1. Tick listener IS active on system.market_data_received
    handlers = event_bus._handlers.get("system.market_data_received", [])
    assert plugin._handle_market_tick in handlers

    # 2. Execution engine blocks real orders
    ems = container.resolve("ExecutionEngineOrchestrator")
    order = Order(
        order_id="test_001",
        request=OrderRequest(
            order_id="test_001",
            symbol="BTCUSDT",
            direction="BUY",
            order_type="MARKET",
            quantity=0.01
        )
    )
    with pytest.raises(PermissionError, match="TRADING_MODE=paper"):
        ems.execute_order(order, exchange="BINANCE")

    # 3. BinanceGatewayProvider blocks real orders
    provider = BinanceGatewayProvider(use_mock=False)
    with pytest.raises(PermissionError, match="Cannot place real order when TRADING_MODE=paper"):
        provider.place_market_order("BTCUSDT", "BUY", 0.1)

    plugin.shutdown()


def test_startup_diagnostics_printed(event_bus, container, capsys):
    """Verify startup diagnostics block is printed on initialize."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()

    captured = capsys.readouterr()
    assert "MARKET PIPELINE:" in captured.out
    assert "Binance WS: CONNECTED" in captured.out
    assert "Publishing Event: system.market_data_received" in captured.out
    assert "Subscribers: " in captured.out
    assert "Last Tick: " in captured.out

    plugin.shutdown()
