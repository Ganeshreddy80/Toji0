"""Unit tests for the Risk Engine Subsystem Plugin."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus, IEvent
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from risk_engine.core.plugin import RiskEnginePlugin
from risk_engine.core.interfaces import (
    IRiskStateStore,
    IRiskRepository,
    IRiskEngine,
)
from risk_engine.core.orchestrator import RiskOrchestrator
from risk_engine.core.events import (
    RiskInitialized,
    RiskShutdown,
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
    """Verify plugin metadata properties."""
    plugin = RiskEnginePlugin()
    assert plugin.plugin_id == PluginId("risk_engine")
    assert plugin.name == "Risk Engine"
    assert plugin.version == "1.0.0"
    assert PluginId("trading_context") in plugin.dependencies


def test_plugin_initialize_and_shutdown(container, event_bus, mock_config_provider):
    """Verify lifecycle transitions, container bindings, and event emission."""
    container.register(IEventBus, instance=event_bus)
    container.register(IConfigProvider, instance=mock_config_provider)

    plugin = RiskEnginePlugin(
        event_bus=event_bus,
        config_provider=mock_config_provider,
        container=container,
    )

    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY

    received_events = []
    event_bus.subscribe("system.risk_initialized", received_events.append)
    event_bus.subscribe("system.risk_shutdown", received_events.append)

    plugin.initialize()

    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY

    # Verify registered in DI container
    assert container.has(IRiskStateStore)
    assert container.has(IRiskRepository)
    assert container.has(IRiskEngine)
    assert container.has(RiskOrchestrator)

    # Initialized event published
    assert len(received_events) == 1
    assert isinstance(received_events[0], RiskInitialized)

    plugin.shutdown()

    assert plugin.state == ModuleState.STOPPED
    assert plugin.health_check() == HealthStatus.UNHEALTHY

    # Shutdown event published
    assert len(received_events) == 2
    assert isinstance(received_events[1], RiskShutdown)


def test_plugin_event_processing(container, event_bus):
    """Verify plugin catches trading context events and forwards to orchestrator."""
    container.register(IEventBus, instance=event_bus)

    mock_orchestrator = MagicMock(spec=RiskOrchestrator)
    mock_orchestrator.process_context = MagicMock()

    plugin = RiskEnginePlugin(
        event_bus=event_bus,
        container=container,
        orchestrator=mock_orchestrator,
    )

    plugin.initialize()

    # Reconstruct a dummy context payload
    dt_iso = "2026-06-26T12:00:00+00:00"
    context_dict = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "market_state": {"symbol": "BTCUSDT", "timeframe": "1h", "updated_at": dt_iso},
        "strategy_state": {"symbol": "BTCUSDT", "timeframe": "1h", "updated_at": dt_iso},
        "generated_at": dt_iso,
    }

    event = MockEvent("system.trading_context_created", {"context": context_dict})
    event_bus.publish(event)

    # Verify orchestrator was called
    mock_orchestrator.process_context.assert_called_once()
