import pytest
from toji_platform.core.types import ModuleState, PluginId
from portfolio_engine.core.state import PortfolioStateStore
from portfolio_engine.core.repository import PortfolioRepository
from portfolio_engine.core.orchestrator import PortfolioOrchestrator
from portfolio_engine.core.plugin import PortfolioPlatformPlugin


class MockContainer:
    def __init__(self):
        self.registrations = {}

    def register(self, key, instance):
        self.registrations[key] = instance

    def has(self, key):
        return key in self.registrations

    def resolve(self, key):
        return self.registrations[key]


class MockEventBus:
    def __init__(self):
        self.subs = []

    def subscribe(self, event_type, handler):
        self.subs.append((event_type, handler))

    def unsubscribe(self, event_type, handler):
        self.subs.remove((event_type, handler))


def test_plugin_lifecycle():
    bus = MockEventBus()
    container = MockContainer()
    container.register("event_bus", bus)
    
    plugin = PortfolioPlatformPlugin(
        event_bus=bus,
        container=container,
    )

    assert plugin.plugin_id == PluginId("portfolio_engine")
    assert plugin.state == ModuleState.CREATED

    # Initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert len(bus.subs) == 3

    # Check DI container registrations
    assert container.has(PortfolioStateStore)
    assert container.has(PortfolioRepository)
    assert container.has(PortfolioOrchestrator)

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
    assert len(bus.subs) == 0
