import pytest
from unittest.mock import MagicMock, patch

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from dashboard.core.plugin import DashboardPlatformPlugin
from dashboard.core.events import DashboardInitialized, DashboardShutdown


@pytest.fixture
def container() -> Container:
    return Container()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def mock_config_provider() -> MagicMock:
    provider = MagicMock(spec=IConfigProvider)
    provider.get.return_value = 8000
    return provider


def test_plugin_metadata() -> None:
    """Verify plugin identity metadata and dependencies."""
    plugin = DashboardPlatformPlugin()
    assert plugin.plugin_id == PluginId("dashboard_platform")
    assert plugin.name == "Dashboard Platform"
    assert plugin.version == "1.0.0"
    assert PluginId("market_intelligence") in plugin.dependencies
    assert PluginId("price_action") in plugin.dependencies
    assert PluginId("confluence") in plugin.dependencies
    assert PluginId("strategy") in plugin.dependencies
    assert PluginId("trading_context") in plugin.dependencies
    assert PluginId("risk_engine") in plugin.dependencies
    assert PluginId("position_sizing") in plugin.dependencies


@patch("dashboard.core.plugin.DashboardPlatformPlugin._start_uvicorn_server")
@patch("dashboard.core.plugin.DashboardPlatformPlugin._stop_uvicorn_server")
def test_plugin_initialize_and_shutdown(
    mock_stop_server: MagicMock,
    mock_start_server: MagicMock,
    container: Container,
    event_bus: InMemoryEventBus,
    mock_config_provider: MagicMock,
) -> None:
    """Verify registration in DI container, event bus subscription, and graceful shutdown."""
    container.register(IEventBus, instance=event_bus)
    container.register(IConfigProvider, instance=mock_config_provider)

    plugin = DashboardPlatformPlugin(
        event_bus=event_bus,
        config_provider=mock_config_provider,
        container=container,
    )

    # Health check before running
    assert plugin.state == ModuleState.CREATED
    assert plugin.health_check() == HealthStatus.UNHEALTHY

    # Record initialization events
    received_events = []
    event_bus.subscribe("dashboard_initialized", received_events.append)
    event_bus.subscribe("dashboard_shutdown", received_events.append)

    # Initialize
    plugin.initialize()

    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY
    mock_start_server.assert_called_once()

    # Verify registered in DI container
    assert container.has(IEventBus) is True

    # Shutdown
    plugin.shutdown()

    assert plugin.state == ModuleState.STOPPED
    mock_stop_server.assert_called_once()
