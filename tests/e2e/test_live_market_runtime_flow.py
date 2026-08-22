"""Tests verifying the live market data event loop and pipeline liveness.
"""

from __future__ import annotations

import os
import time
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataReceived
from market_gateway.providers.binance.client import BinanceGatewayProvider
from research_platform.live_trading.factory import MarketProviderFactory
from research_platform.live_trading.plugin import LiveTradingEnginePlugin
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator


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


class AsyncContextManagerMock:
    """Mock for websockets.connect async context manager."""
    def __init__(self, ws_mock):
        self.ws_mock = ws_mock

    async def __aenter__(self):
        return self.ws_mock

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture(autouse=True)
def clean_env():
    """Save and restore environment variables and mock networks around each test."""
    saved = {}
    for key in ("MARKET_PROVIDER", "TRADING_MODE", "APP_ENV"):
        saved[key] = os.environ.get(key)
    os.environ["APP_ENV"] = "testing"
    
    # Clean up state manager fallback store
    from toji_platform.runtime.state import RuntimeStateManager
    RuntimeStateManager._fallback_store.clear()
    
    # Mock websockets connect and get_server_time globally to run completely offline
    ws_mock = MagicMock()
    ws_mock.recv = MagicMock(side_effect=lambda: asyncio.sleep(3600))
    ws_mock.ping = MagicMock(return_value=asyncio.Future())
    ws_mock.ping.return_value.set_result(None)
    
    async def mock_send(data):
        return None
    ws_mock.send = mock_send

    async def mock_close():
        return None
    ws_mock.close = mock_close
    
    ws_ctx = AsyncContextManagerMock(ws_mock)
    
    with patch("websockets.connect", return_value=ws_ctx):
        with patch("market_gateway.providers.binance.exchange.BinanceExchangeProvider.get_server_time", return_value=int(time.time() * 1000)):
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


def test_binance_websocket_task_running(event_bus, container):
    """Verify that starting the gateway correctly spawns the background task thread."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    gateway.start()

    assert gateway._provider is not None
    assert gateway._provider._ws_task is not None
    assert not gateway._provider._ws_task.done()

    gateway.stop()


def test_real_tick_reaches_event_bus(event_bus, container):
    """Verify that a raw WS incoming message is processed, normalized, and published."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    gateway.start()

    ticks = []
    event_bus.subscribe("system.market_data_received", ticks.append)

    raw_tick = {
        "e": "trade",
        "E": 1712345678901,
        "s": "BTCUSDT",
        "p": "95000.5",
        "q": "0.1",
        "T": 1712345678901,
        "t": 98765432,
        "m": False
    }
    gateway._provider._handle_ws_message(raw_tick)

    assert len(ticks) == 1
    assert ticks[0].payload["symbol"] == "BTCUSDT"
    assert ticks[0].payload["price"] == 95000.5
    assert ticks[0].payload["volume"] == 0.1

    gateway.stop()


def test_tick_updates_runtime_state(event_bus, container):
    """Verify that processing a tick successfully updates the state manager metrics."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    from toji_platform.runtime.state import RuntimeStateManager
    sm = RuntimeStateManager()
    sm.load()
    sm.processed_ticks = 0
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
    assert sm.processed_ticks > 0
    assert sm.last_tick_time is not None

    plugin.shutdown()


def test_feature_generated_after_tick(event_bus, container):
    """Verify that tick propagation triggers feature calculations."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    from research_platform.price_action.orchestrator import PriceActionOrchestrator
    from research_platform.price_action.repository import PriceActionRepository
    from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator

    repo = PriceActionRepository()
    pa_orch = PriceActionOrchestrator(event_bus=event_bus, repository=repo, container=container)
    fp_orch = FeaturePlatformOrchestrator(event_bus)

    container.register("PriceActionOrchestrator", pa_orch)
    container.register("FeaturePlatformOrchestrator", fp_orch)

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

    stored = fp_orch.store.query_latest(["close", "rsi"], ["BTCUSDT"])
    assert not stored.empty

    plugin.shutdown()


def test_paper_mode_full_pipeline(event_bus, container):
    """Verify that paper mode executes full pipeline from tick to ingested signal."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    from research_platform.price_action.orchestrator import PriceActionOrchestrator
    from research_platform.price_action.repository import PriceActionRepository
    from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator

    repo = PriceActionRepository()
    pa_orch = PriceActionOrchestrator(event_bus=event_bus, repository=repo, container=container)
    fp_orch = FeaturePlatformOrchestrator(event_bus)

    mock_ai = MagicMock()
    mock_ai.generate_signal.return_value = MagicMock(signal="BUY", confidence=0.85)

    container.register("PriceActionOrchestrator", pa_orch)
    container.register("FeaturePlatformOrchestrator", fp_orch)
    container.register("AISignalGenerator", mock_ai)

    mock_orchestrator = MagicMock()

    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()
    
    # Overwrite orchestrator AFTER initialize to prevent initialization overwriting it
    plugin._orchestrator = mock_orchestrator

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

    assert mock_orchestrator.ingest_market_signal.called
    args = mock_orchestrator.ingest_market_signal.call_args[0][0]
    assert args.symbol == "BTCUSDT"
    assert args.direction == "BUY"
    assert args.strength == 0.85

    plugin.shutdown()
