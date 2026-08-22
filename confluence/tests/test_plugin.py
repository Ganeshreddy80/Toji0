"""Unit tests for the Confluence Subsystem Plugin."""

from __future__ import annotations

import pytest

from confluence.core.exceptions import ConfluenceException
from confluence.core.interfaces import (
    IConfluenceEngine,
    IConfluenceRepository,
    IConfluenceStateStore,
)
from confluence.core.plugin import ConfluencePlugin
from confluence.core.orchestrator import ConfluenceOrchestrator
from toji_platform.core.configuration import ConfigurationManager
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from market_intelligence.core.interfaces import IStateStore
from market_intelligence.core.state import MarketIntelligenceState
from price_action.core.interfaces import IPatternStateStore
from price_action.core.state import PriceActionStateStore
from confluence.core.state import ConfluenceStateStore
from confluence.core.repository import ConfluenceRepository
from confluence.analysis.confluence_engine import ConfluenceEngine


def test_plugin_metadata():
    """Verify plugin identity and dependency attributes."""
    plugin = ConfluencePlugin()
    assert plugin.plugin_id == PluginId("confluence")
    assert plugin.name == "Confluence Engine"
    assert plugin.version == "1.0.0"
    assert PluginId("market_intelligence") in plugin.dependencies
    assert PluginId("price_action") in plugin.dependencies
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY  # Not running yet


def test_plugin_lifecycle_manual_injection():
    """Verify initialization and shutdown with constructor-injected services."""
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    # We must register state stores because the orchestrator will look for them
    market_store = MarketIntelligenceState()
    pattern_store = PriceActionStateStore()

    state_store = ConfluenceStateStore()
    repo = ConfluenceRepository()
    engine = ConfluenceEngine()
    orchestrator = ConfluenceOrchestrator()

    # Inject state stores directly to orchestrator
    orchestrator.initialize(
        confluence_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
        market_state_store=market_store,
        pattern_state_store=pattern_store,
    )

    plugin = ConfluencePlugin(
        event_bus=bus,
        config_provider=config,
        state_store=state_store,
        repository=repo,
        confluence_engine=engine,
        orchestrator=orchestrator,
    )

    assert plugin.state == ModuleState.CREATED

    # Initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY
    assert isinstance(plugin.state_store, IConfluenceStateStore)
    assert isinstance(plugin.repository, IConfluenceRepository)

    # Check that subscriptions are registered
    assert bus.has_subscribers("system.market_state_updated")
    assert bus.has_subscribers("system.pattern_updated")
    assert bus.has_subscribers("system.pattern_quality_updated")

    # Double initialization is idempotent
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
    assert not bus.has_subscribers("system.market_state_updated")
    assert not bus.has_subscribers("system.pattern_updated")
    assert not bus.has_subscribers("system.pattern_quality_updated")


def test_plugin_initialization_missing_bus_raises():
    """Verify initialization failure if event bus is missing."""
    plugin = ConfluencePlugin()
    with pytest.raises(ConfluenceException, match="Event Bus is required"):
        plugin.initialize()
    assert plugin.state == ModuleState.FAILED


def test_plugin_lifecycle_container_resolution():
    """Verify initialization and shutdown resolving dependencies from Container."""
    container = Container()
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    market_store = MarketIntelligenceState()
    pattern_store = PriceActionStateStore()

    # Register core services
    container.register(IEventBus, instance=bus)
    container.register(IConfigProvider, instance=config)
    container.register(IStateStore, instance=market_store)
    container.register(IPatternStateStore, instance=pattern_store)

    # Build plugin and register in container
    plugin = ConfluencePlugin(container=container)
    assert plugin.state == ModuleState.CREATED

    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Verify StateStore and Repository registered in Container
    assert container.has(IConfluenceStateStore)
    assert container.has(IConfluenceRepository)
    assert container.has(IConfluenceEngine)
    assert container.has(ConfluenceOrchestrator)

    assert container.resolve(IConfluenceStateStore) == plugin.state_store
    assert container.resolve(IConfluenceRepository) == plugin.repository

    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
