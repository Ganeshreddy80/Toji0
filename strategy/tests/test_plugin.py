"""Unit tests for the Strategy Subsystem Plugin."""

from __future__ import annotations

import pytest

from strategy.core.exceptions import StrategyException
from strategy.core.interfaces import (
    IStrategyEngine,
    IStrategyRepository,
    IStrategyStateStore,
)
from strategy.core.plugin import StrategyPlugin
from strategy.core.orchestrator import StrategyOrchestrator
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
from confluence.core.interfaces import IConfluenceStateStore
from confluence.core.state import ConfluenceStateStore
from strategy.core.state import StrategyStateStore
from strategy.core.repository import StrategyRepository
from strategy.analysis.strategy_engine import StrategyEngine


def test_plugin_metadata():
    """Verify plugin identity and dependency attributes."""
    plugin = StrategyPlugin()
    assert plugin.plugin_id == PluginId("strategy")
    assert plugin.name == "Strategy Engine"
    assert plugin.version == "1.0.0"
    assert PluginId("market_intelligence") in plugin.dependencies
    assert PluginId("price_action") in plugin.dependencies
    assert PluginId("confluence") in plugin.dependencies
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY  # Not running yet


def test_plugin_lifecycle_manual_injection():
    """Verify initialization and shutdown with constructor-injected services."""
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    market_store = MarketIntelligenceState()
    pattern_store = PriceActionStateStore()
    confluence_store = ConfluenceStateStore()

    state_store = StrategyStateStore()
    repo = StrategyRepository()
    engine = StrategyEngine()
    orchestrator = StrategyOrchestrator()

    # Inject state stores directly to orchestrator
    orchestrator.initialize(
        strategy_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
        market_state_store=market_store,
        pattern_state_store=pattern_store,
        confluence_state_store=confluence_store,
    )

    plugin = StrategyPlugin(
        event_bus=bus,
        config_provider=config,
        state_store=state_store,
        repository=repo,
        strategy_engine=engine,
        orchestrator=orchestrator,
    )

    assert plugin.state == ModuleState.CREATED

    # Initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY
    assert isinstance(plugin.state_store, IStrategyStateStore)
    assert isinstance(plugin.repository, IStrategyRepository)

    # Check that subscriptions are registered
    assert bus.has_subscribers("system.market_state_updated")
    assert bus.has_subscribers("system.pattern_updated")
    assert bus.has_subscribers("system.pattern_quality_updated")
    assert bus.has_subscribers("system.confluence_updated")

    # Double initialization is idempotent
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
    assert not bus.has_subscribers("system.market_state_updated")
    assert not bus.has_subscribers("system.pattern_updated")
    assert not bus.has_subscribers("system.pattern_quality_updated")
    assert not bus.has_subscribers("system.confluence_updated")


def test_plugin_initialization_missing_bus_raises():
    """Verify initialization failure if event bus is missing."""
    plugin = StrategyPlugin()
    with pytest.raises(StrategyException, match="Event Bus is required"):
        plugin.initialize()
    assert plugin.state == ModuleState.FAILED


def test_plugin_lifecycle_container_resolution():
    """Verify initialization and shutdown resolving dependencies from Container."""
    container = Container()
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    market_store = MarketIntelligenceState()
    pattern_store = PriceActionStateStore()
    confluence_store = ConfluenceStateStore()

    # Register core services
    container.register(IEventBus, instance=bus)
    container.register(IConfigProvider, instance=config)
    container.register(IStateStore, instance=market_store)
    container.register(IPatternStateStore, instance=pattern_store)
    container.register(IConfluenceStateStore, instance=confluence_store)

    # Build plugin and register in container
    plugin = StrategyPlugin(container=container)
    assert plugin.state == ModuleState.CREATED

    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # Verify StateStore and Repository registered in Container
    assert container.has(IStrategyStateStore)
    assert container.has(IStrategyRepository)
    assert container.has(IStrategyEngine)
    assert container.has(StrategyOrchestrator)

    assert container.resolve(IStrategyStateStore) == plugin.state_store
    assert container.resolve(IStrategyRepository) == plugin.repository

    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
