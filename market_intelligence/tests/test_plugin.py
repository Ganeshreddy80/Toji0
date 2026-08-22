"""Unit tests for the Market Intelligence Layer Plugin."""

from __future__ import annotations

import pytest

from market_intelligence.core.exceptions import PluginInitializationError
from market_intelligence.core.interfaces import IRepository, IStateStore
from market_intelligence.core.plugin import MarketIntelligencePlugin
from toji_platform.core.configuration import ConfigurationManager
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState, PluginId


def test_plugin_metadata():
    """Verify plugin identity and dependency attributes."""
    plugin = MarketIntelligencePlugin()
    assert plugin.plugin_id == PluginId("market_intelligence")
    assert plugin.name == "Market Intelligence"
    assert plugin.version == "1.0.0"
    assert PluginId("market_gateway") in plugin.dependencies
    assert PluginId("universe_manager") in plugin.dependencies
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY  # Not running yet


def test_plugin_lifecycle_manual_injection():
    """Verify initialization and shutdown with constructor-injected services."""
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    plugin = MarketIntelligencePlugin(event_bus=bus, config_provider=config)
    assert plugin.state == ModuleState.CREATED

    # Initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY
    assert isinstance(plugin.state_store, IStateStore)
    assert isinstance(plugin.repository, IRepository)

    # Check that subscriptions are registered
    assert bus.has_subscribers("system.market_data_updated")
    assert bus.has_subscribers("system.universe_updated")

    # Double initialization is idempotent
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
    assert not bus.has_subscribers("system.market_data_updated")
    assert not bus.has_subscribers("system.universe_updated")

    # Double shutdown is idempotent
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED


def test_plugin_initialization_missing_bus_raises():
    """Verify initialization failure if event bus is missing."""
    plugin = MarketIntelligencePlugin()
    with pytest.raises(PluginInitializationError, match="Event Bus is required"):
        plugin.initialize()
    assert plugin.state == ModuleState.FAILED


def test_plugin_lifecycle_container_resolution():
    """Verify initialization and shutdown resolving dependencies from Container."""
    container = Container()
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    # Register core services
    container.register(IEventBus, instance=bus)
    container.register(IConfigProvider, instance=config)

    # Build plugin and register in container
    plugin = MarketIntelligencePlugin(container=container)
    assert plugin.state == ModuleState.CREATED

    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Verify StateStore and Repository registered in Container
    assert container.has(IStateStore)
    assert container.has(IRepository)
    assert container.resolve(IStateStore) == plugin.state_store
    assert container.resolve(IRepository) == plugin.repository

    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED



def test_plugin_event_callbacks():
    """Verify that event callbacks are registered and executed without error."""
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    plugin = MarketIntelligencePlugin(event_bus=bus, config_provider=config)
    plugin.initialize()

    # Publish event to bus and verify handlers don't crash
    from toji_platform.core.event_bus.events import MarketDataUpdated
    from universe.core.events import UniverseUpdated

    bus.publish(MarketDataUpdated(source="test", payload={}))
    bus.publish(UniverseUpdated(source="test", payload={}))

    plugin.shutdown()
