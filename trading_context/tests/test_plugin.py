"""Unit tests for the Trading Context Subsystem Plugin."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus, IEvent
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from trading_context.core.plugin import TradingContextPlugin
from trading_context.core.interfaces import (
    ITradingContextStateStore,
    ITradingContextRepository,
)
from trading_context.core.orchestrator import TradingContextOrchestrator
from trading_context.core.events import (
    TradingContextInitialized,
    TradingContextShutdown,
)


class MockEvent(IEvent):
    def __init__(self, event_type: str, payload: dict) -> None:
        self._event_type = event_type
        self._payload = payload

    @property
    def event_type(self) -> str:
        return self._event_type

    @property
    def source(self) -> str:
        return "test"

    @property
    def payload(self) -> dict:
        return self._payload


@pytest.fixture
def container() -> Container:
    return Container()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def mock_config_provider() -> MagicMock:
    provider = MagicMock(spec=IConfigProvider)
    provider.get.return_value = 1000
    return provider


def test_plugin_metadata():
    """Verify plugin identity metadata and dependencies."""
    plugin = TradingContextPlugin()
    assert plugin.plugin_id == PluginId("trading_context")
    assert plugin.name == "Trading Context"
    assert plugin.version == "1.0.0"
    assert PluginId("market_intelligence") in plugin.dependencies
    assert PluginId("price_action") in plugin.dependencies
    assert PluginId("confluence") in plugin.dependencies
    assert PluginId("strategy") in plugin.dependencies


def test_plugin_initialize_and_shutdown(container, event_bus, mock_config_provider):
    """Verify registration in DI container, event bus subscription, and graceful shutdown."""
    # 1. Register IEventBus and IConfigProvider in the container
    container.register(IEventBus, instance=event_bus)
    container.register(IConfigProvider, instance=mock_config_provider)

    plugin = TradingContextPlugin(
        event_bus=event_bus,
        config_provider=mock_config_provider,
        container=container,
    )

    # Health check before running
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY

    # Record initialization events
    received_events = []
    event_bus.subscribe("system.trading_context_initialized", received_events.append)
    event_bus.subscribe("system.trading_context_shutdown", received_events.append)

    # Initialize
    plugin.initialize()

    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY

    # Verify registered in DI container
    assert container.has(ITradingContextStateStore)
    assert container.has(ITradingContextRepository)
    assert container.has(TradingContextOrchestrator)

    # Verify that TradingContextInitialized event was published
    assert len(received_events) == 1
    assert isinstance(received_events[0], TradingContextInitialized)

    # Shutdown
    plugin.shutdown()

    assert plugin.state == ModuleState.STOPPED
    assert plugin.health_check() == HealthStatus.UNHEALTHY

    # Verify that TradingContextShutdown event was published
    assert len(received_events) == 2
    assert isinstance(received_events[1], TradingContextShutdown)

    # Verify subscriptions are cleared
    assert len(plugin._active_subscriptions) == 0


def test_plugin_event_processing(container, event_bus):
    """Verify plugin catches upstream events and triggers orchestrator process_context."""
    container.register(IEventBus, instance=event_bus)

    # Mock the orchestrator
    mock_orchestrator = MagicMock(spec=TradingContextOrchestrator)
    mock_orchestrator.process_context = MagicMock()

    plugin = TradingContextPlugin(
        event_bus=event_bus,
        container=container,
        orchestrator=mock_orchestrator,
    )

    plugin.initialize()

    # Publish an event to the bus
    event_payload = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "state": {"symbol": "BTCUSDT", "timeframe": "1h"},
    }
    market_event = MockEvent("system.market_state_updated", event_payload)
    event_bus.publish(market_event)

    # Verify that orchestrator was called
    mock_orchestrator.process_context.assert_called_once_with("BTCUSDT", "1h")
