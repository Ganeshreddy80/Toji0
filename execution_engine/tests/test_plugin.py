from typing import Any, Type
import time

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

from execution_engine.core.interfaces import IExecutionEngine, IExecutionRepository, IExecutionStateStore
from execution_engine.core.plugin import ExecutionEnginePlugin
from execution_engine.tests.test_orchestrator import MockEventBus


class MockConfigProvider(IConfigProvider):
    """Mock configuration provider for testing."""

    @property
    def profile(self) -> Any:
        from toji_platform.core.types import Profile
        return Profile("test")

    def get(self, key: str, default: Any = None) -> Any:
        return default

    def get_required(self, key: str) -> Any:
        return None

    def get_section(self, prefix: str) -> dict[str, Any]:
        return {}

    def set(self, key: str, value: Any) -> None:
        pass

    def validate(self, required_keys: list[str]) -> None:
        pass

    def all(self) -> dict[str, Any]:
        return {}


class MockContainer(IContainer):
    """Mock Dependency Injection Container for testing."""

    def __init__(self) -> None:
        self.services = {}

    def register(self, interface: Any, instance: Any = None, factory: Any = None, *, singleton: bool = True) -> None:
        self.services[interface] = instance

    def resolve(self, interface: Any) -> Any:
        return self.services[interface]

    def has(self, interface: Any) -> bool:
        return interface in self.services

    def reset(self) -> None:
        self.services.clear()


def test_plugin_lifecycle():
    bus = MockEventBus()
    config = MockConfigProvider()
    container = MockContainer()
    
    # Pre-register common services in container
    container.register(IEventBus, bus)
    container.register(IConfigProvider, config)
    
    plugin = ExecutionEnginePlugin(container=container)
    assert plugin.state == ModuleState.CREATED
    assert plugin.plugin_id == PluginId("execution_engine")
    
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    
    # Allow background broker connection monitor thread to set status to CONNECTED
    time.sleep(0.05)
    
    # Resolve services from container to verify successful registration
    assert container.has(IExecutionStateStore) is True
    assert container.has(IExecutionRepository) is True
    assert container.has(IExecutionEngine) is True
    
    assert plugin.health_check() == HealthStatus.HEALTHY
    
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED


def test_execution_engine_plugin_partial_shutdown_rollback():
    import pytest
    from execution_engine.core.exceptions import ExecutionEngineError

    config = MockConfigProvider()
    container = MockContainer()
    container.register(IConfigProvider, config)
    
    plugin = ExecutionEnginePlugin(container=container)
    assert plugin.state == ModuleState.CREATED
    
    with pytest.raises(ExecutionEngineError):
        plugin.initialize()
        
    assert plugin.state == ModuleState.FAILED
    
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED
