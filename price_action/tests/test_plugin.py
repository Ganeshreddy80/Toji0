"""Unit tests for the Price Action Engine plugin lifecycle and DI integration."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from market_intelligence.core.events import MarketStateUpdated
from market_intelligence.core.models import MarketState
from price_action.core.events import PriceActionInitialized, PriceActionShutdown
from price_action.core.exceptions import PriceActionException
from price_action.core.plugin import PriceActionPlugin
from price_action.core.orchestrator import PriceActionOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.dependency_injection import Container
from toji_platform.core.types import HealthStatus, ModuleState, PluginId


def test_plugin_metadata():
    """Verify basic metadata fields of the Price Action plugin."""
    plugin = PriceActionPlugin()
    assert plugin.plugin_id == PluginId("price_action")
    assert plugin.name == "Price Action Engine"
    assert plugin.version == "1.0.0"
    assert plugin.dependencies == [PluginId("market_intelligence")]
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY  # NOT RUNNING YET


def test_plugin_lifecycle_wiring():
    """Verify plugin initialization, container dependency registration, and shutdown."""
    container = Container()
    bus = InMemoryEventBus()
    container.register("IEventBus", instance=bus)
    from toji_platform.core.event_bus.interfaces import IEventBus as IBusInterface
    container.register(IBusInterface, instance=bus)

    plugin = PriceActionPlugin(container=container, event_bus=bus)
    assert plugin.state == ModuleState.CREATED

    # Initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY

    # Verify registered container elements
    from price_action.core.interfaces import IPatternStateStore, IPatternRepository
    assert container.has(IPatternStateStore)
    assert container.has(IPatternRepository)
    assert container.has(PriceActionOrchestrator)

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
    assert plugin.health_check() == HealthStatus.UNHEALTHY


def test_plugin_missing_bus_raises():
    """Verify plugin initialisation fails if event bus is missing."""
    plugin = PriceActionPlugin(event_bus=None)
    with pytest.raises(PriceActionException):
        plugin.initialize()


class MockPriceActionOrchestrator:
    """Mock orchestrator to track candle state processing."""

    def __init__(self) -> None:
        self.processed_states = []

    def initialize(self, *args, **kwargs) -> None:
        pass

    def process_market_state(self, market_state: MarketState) -> Any:
        self.processed_states.append(market_state)
        return None


def test_plugin_event_callbacks():
    """Verify that plugin callback parses MarketStateUpdated event and routes to orchestrator."""
    bus = InMemoryEventBus()
    orch = MockPriceActionOrchestrator()
    plugin = PriceActionPlugin(event_bus=bus, orchestrator=orch) # type: ignore[arg-type]
    plugin.initialize()

    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=[],
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        sr_levels=[],
        structure_history=[],
        bos_history=[],
        choch_history=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=dt,
    )

    # Simulate MIL publishing MarketStateUpdated
    state_event = MarketStateUpdated(
        source="mil_orchestrator",
        payload={
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "state": market_state.model_dump(mode="json"),
        },
    )
    bus.publish(state_event)

    # Verify orchestrator callback routing
    assert len(orch.processed_states) == 1
    assert orch.processed_states[0].symbol == "BTCUSDT"
    assert orch.processed_states[0].timeframe == "1h"
