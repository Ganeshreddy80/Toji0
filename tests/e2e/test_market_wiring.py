"""Tests for decoupling market provider from execution mode, safety gates, and duplicate executions.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketTickReceived
from market_gateway.providers.binance.exchange import BinanceExchangeProvider
from market_gateway.providers.binance.client import BinanceGatewayProvider
from research_platform.live_trading.factory import MarketProviderFactory, BinanceMarketGateway
from research_platform.live_trading.binance_demo import BinanceDemoGateway
from research_platform.live_trading.plugin import LiveTradingEnginePlugin
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.oms.models import Order, OrderRequest


class DummyContainer:
    """Simple container implementation for test assertions."""

    def __init__(self):
        self._services = {}

    def register(self, key, instance):
        self._services[key] = instance

    def resolve(self, key):
        return self._services[key]

    def has(self, key):
        return key in self._services


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


def test_paper_uses_real_market_provider(event_bus, container):
    """Verify that paper trading mode can use a real live market provider."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    os.environ["TRADING_MODE"] = "paper"

    # Pre-register provider in container to simulate boot.py reuse
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert isinstance(gateway, BinanceMarketGateway)
    assert gateway.ws_url == "wss://stream.binance.com:9443/ws"

    # Start gateway
    gateway.start()
    assert gateway.running is True
    assert provider.use_mock is False
    assert provider._ws_url == "wss://stream.binance.com:9443/ws"
    
    gateway.stop()


def test_demo_provider_requires_explicit_config(event_bus, container):
    """Verify that demo provider must be explicitly set and resolves correctly."""
    # 1. Missing MARKET_PROVIDER raises ValueError
    if "MARKET_PROVIDER" in os.environ:
        del os.environ["MARKET_PROVIDER"]

    with pytest.raises(ValueError, match="MARKET_PROVIDER environment variable must be explicitly configured"):
        MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)

    # 2. Configured to demo resolves to BinanceDemoGateway
    os.environ["MARKET_PROVIDER"] = "demo"
    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert isinstance(gateway, BinanceDemoGateway)


def test_live_execution_disabled_in_paper_mode(event_bus, container):
    """Verify that if TRADING_MODE=paper, live orders are blocked at both layers."""
    os.environ["TRADING_MODE"] = "paper"

    # 1. Blocked at EMS orchestrator level
    ems = container.resolve("ExecutionEngineOrchestrator")
    req = OrderRequest(order_id="o1", symbol="BTC/USDT", direction="BUY", quantity=0.1, order_type="MARKET")
    order = Order(order_id="o1", request=req, status="ROUTED")

    with pytest.raises(PermissionError, match="Real exchange orders are blocked when TRADING_MODE=paper"):
        ems.execute_order(order, exchange="BINANCE")

    # 2. Blocked at Provider level when use_mock=False
    provider = BinanceGatewayProvider(use_mock=False)
    with pytest.raises(PermissionError, match="Cannot place real order when TRADING_MODE=paper"):
        provider.place_market_order("BTCUSDT", "BUY", 0.1)

    with pytest.raises(PermissionError, match="Cannot place real order when TRADING_MODE=paper"):
        provider.place_limit_order("BTCUSDT", "BUY", 0.1, 95000.0)


def test_no_duplicate_order_execution(event_bus, container):
    """Verify that tick listener is ACTIVE in both paper and live modes.

    Market data must always flow. Execution safety (blocking real orders in paper
    mode) is enforced by ExecutionEngineOrchestrator, not by disabling the listener.
    """
    os.environ["MARKET_PROVIDER"] = "demo"
    os.environ["TRADING_MODE"] = "paper"

    plugin = LiveTradingEnginePlugin(container)
    plugin.initialize()

    # Tick listener MUST be subscribed even in paper mode
    handlers = event_bus._handlers.get("system.market_data_received", [])
    assert plugin._handle_market_tick in handlers

    # Clean up before next plugin
    plugin.shutdown()

    # Set TRADING_MODE to live and test registration
    os.environ["TRADING_MODE"] = "live"
    plugin_live = LiveTradingEnginePlugin(container)
    plugin_live.initialize()

    handlers_live = event_bus._handlers.get("system.market_data_received", [])
    assert plugin_live._handle_market_tick in handlers_live

    # Clean up subscriptions
    plugin_live.shutdown()



def test_binance_live_never_uses_demo_url(event_bus, container):
    """Verify that binance_live resolves exactly to api.binance.com and stream.binance.com without demo keywords."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert gateway.rest_url == "https://api.binance.com/api"
    assert gateway.ws_url == "wss://stream.binance.com:9443/ws"
    assert "demo" not in gateway.rest_url
    assert "demo" not in gateway.ws_url


def test_testnet_uses_testnet_url(event_bus, container):
    """Verify that binance_testnet resolves to testnet.binance.vision URLs."""
    os.environ["MARKET_PROVIDER"] = "binance_testnet"
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert gateway.rest_url == "https://testnet.binance.vision/api"
    assert gateway.ws_url == "wss://testnet.binance.vision/ws"
    assert "demo" not in gateway.rest_url
    assert "demo" not in gateway.ws_url


def test_demo_is_explicit_only(event_bus, container):
    """Verify that demo is the only provider that resolves to BinanceDemoGateway."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert not isinstance(gateway, BinanceDemoGateway)

    os.environ["MARKET_PROVIDER"] = "demo"
    gateway_demo = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    assert isinstance(gateway_demo, BinanceDemoGateway)


def test_paper_mode_receives_real_market_ticks(event_bus, container):
    """Verify that in paper mode, BinanceMarketGateway receives, normalizes, and publishes events."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    gateway.start()

    ticks = []
    event_bus.subscribe("system.market_data_received", lambda e: ticks.append(e))

    raw_tick = {
        "e": "trade",
        "E": 1712345678901,
        "s": "BTCUSDT",
        "p": "94200.5",
        "q": "0.05"
    }
    # Publish through provider and check interception
    provider._publish_event(MarketTickReceived, raw_tick)

    assert len(ticks) == 1
    event = ticks[0]
    assert event.source == "BinanceMarketGateway"
    assert event.payload["symbol"] == "BTCUSDT"
    assert event.payload["price"] == 94200.5
    assert event.payload["volume"] == 0.05

    gateway.stop()


def test_no_mock_generator_in_binance_live(event_bus, container):
    """Verify that use_mock is set to False and no mock generator runs when using binance_live."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    provider = BinanceGatewayProvider(use_mock=True)
    container.register(BinanceExchangeProvider, provider)

    gateway = MarketProviderFactory.create_provider(event_bus, ["BTCUSDT"], container)
    gateway.start()

    assert provider.use_mock is False
    assert provider._mock_task is None

    gateway.stop()


def test_binance_live_time_endpoint_correct(event_bus, container, monkeypatch):
    """Verify that requests to the live provider's /v3/time end up as /api/v3/time."""
    os.environ["MARKET_PROVIDER"] = "binance_live"
    provider = BinanceGatewayProvider(use_mock=False)
    container.register(BinanceExchangeProvider, provider)

    requested_urls = []
    def mock_get(url, *args, **kwargs):
        requested_urls.append(url)
        class MockResponse:
            def json(self):
                return {"serverTime": 1712345678900}
            @property
            def status_code(self):
                return 200
        return MockResponse()

    monkeypatch.setattr("httpx.get", mock_get)

    try:
        provider.get_server_time()
    except Exception:
        pass

    assert len(requested_urls) > 0
    assert requested_urls[0].startswith("https://api.binance.com/api/v3/time")


def test_no_duplicate_binance_url_builder():
    """Verify that both BinanceMarketGateway and BinanceExchangeProvider use BinanceEndpointConfig."""
    from market_gateway.providers.binance.config import BinanceEndpointConfig
    from market_gateway.providers.binance.exchange import BinanceExchangeProvider
    from research_platform.live_trading.factory import BinanceMarketGateway
    from toji_platform.core.event_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    class DummyContainer:
        def has(self, key): return False
        def register(self, key, instance): pass

    os.environ["MARKET_PROVIDER"] = "binance_live"
    gateway = BinanceMarketGateway(bus, ["BTCUSDT"], DummyContainer())
    provider = BinanceExchangeProvider(use_mock=False)

    assert gateway.rest_url == "https://api.binance.com/api"
    assert gateway.ws_url == "wss://stream.binance.com:9443/ws"
    assert provider._rest_url == "https://api.binance.com/api"
    assert provider._ws_url == "wss://stream.binance.com:9443/ws"
    assert gateway.endpoint_config.rest_url == provider.endpoint_config.rest_url
    assert gateway.endpoint_config.ws_url == provider.endpoint_config.ws_url
