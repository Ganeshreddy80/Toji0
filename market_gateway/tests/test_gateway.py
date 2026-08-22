"""Unit tests for Market Gateway core coordination and routing."""

from __future__ import annotations

import asyncio
from toji_platform.core.event_bus.bus import InMemoryEventBus
from market_gateway.core.gateway import MarketGateway
from market_gateway.providers.binance.client import BinanceGatewayProvider
from market_gateway.providers.bybit import BybitGatewayProvider
from toji_platform.core.types import HealthStatus, ModuleState


def test_gateway_initialization_and_shutdown():
    async def _run():
        event_bus = InMemoryEventBus()
        gateway = MarketGateway(event_bus)

        assert gateway.name == "Market Gateway"
        assert gateway.state == ModuleState.CREATED

        # Register providers
        binance = BinanceGatewayProvider(use_mock=True)
        bybit = BybitGatewayProvider()

        gateway.register_provider(binance)
        gateway.register_provider(bybit)

        gateway.initialize()
        assert gateway.state == ModuleState.RUNNING
        assert gateway.health_check() == HealthStatus.DEGRADED

        # Verify connection stats exist
        health = gateway.get_detailed_health()
        assert "Binance" in health
        assert health["Binance"]["status"] == "connected"
        assert "Bybit" in health
        assert health["Bybit"]["status"] == "disconnected"

        gateway.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())


def test_gateway_subscriptions():
    async def _run():
        event_bus = InMemoryEventBus()
        gateway = MarketGateway(event_bus)

        binance = BinanceGatewayProvider(use_mock=True)
        gateway.register_provider(binance)
        gateway.initialize()

        # Track published events
        received_events = []
        event_bus.subscribe("system.market_data_updated", received_events.append)

        # Subscribe through gateway
        gateway.subscribe_candles("BTCUSDT", "1m")
        gateway.subscribe_trades("BTCUSDT")
        gateway.subscribe_order_book("BTCUSDT")

        assert ("BTCUSDT", "ohlcv", "1m") in gateway.active_subscriptions
        assert ("BTCUSDT", "trade", "") in gateway.active_subscriptions
        assert ("BTCUSDT", "order_book", "") in gateway.active_subscriptions

        gateway.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())
