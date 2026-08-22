import time
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.core.plugin_manager.manager import PluginManager
from toji_platform.core.plugin_manager.interfaces import IPlugin, IPluginManager
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from toji_platform.core.lifecycle.heartbeat import HeartbeatScheduler

from dashboard.core.state import DashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.core.orchestrator import DashboardOrchestrator
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager
from dashboard.aggregator.event_aggregator import DashboardEventAggregator
from dashboard.backend.app import create_app


# Stub Plugin for Testing
class StubPlatformPlugin(IPlugin):
    def __init__(self, pid: str, name: str) -> None:
        self._pid = PluginId(pid)
        self._name = name
        self._state = ModuleState.CREATED
        self.initialized = False
        self.shutdown_called = False

    @property
    def plugin_id(self) -> PluginId:
        return self._pid

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return []

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        self.initialized = True
        self._state = ModuleState.RUNNING

    def shutdown(self) -> None:
        self.shutdown_called = True
        self._state = ModuleState.STOPPED

    def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY


# Test Event
class DummyPlatformEvent(BaseEvent):
    pass


def test_event_bus_timeline_records_latency():
    """Verify that InMemoryEventBus records dispatches in timeline."""
    bus = InMemoryEventBus()
    
    # 1. Initially timeline is empty
    assert len(bus.get_timeline()) == 0
    
    # 2. Publish an event
    evt = DummyPlatformEvent(source="test-unit", payload={"correlation_id": "test-corr-123"})
    bus.publish(evt)
    
    # 3. Timeline should contain trace
    timeline = bus.get_timeline()
    assert len(timeline) == 1
    trace = timeline[0]
    assert trace["event_id"] == str(evt.event_id)
    assert trace["event_type"] == "system.dummy_platform_event"
    assert trace["source"] == "test-unit"
    assert trace["correlation_id"] == "test-corr-123"
    assert trace["processing_latency_ms"] >= 0.0


def test_plugin_manager_lifecycle_stats():
    """Verify that PluginManager measures startup/shutdown durations and records stats."""
    pm = PluginManager()
    plugin = StubPlatformPlugin("test_plugin", "Test Plugin")
    
    pm.load(plugin)
    stats = pm.get_plugin_lifecycle_stats()
    assert stats["test_plugin"]["state"] == "created"
    
    # Initialize
    pm.initialize_all()
    stats = pm.get_plugin_lifecycle_stats()
    assert stats["test_plugin"]["state"] == "running"
    assert stats["test_plugin"]["startup_duration_ms"] >= 0.0
    assert stats["test_plugin"]["startup_timestamp"] is not None
    assert stats["test_plugin"]["uptime"] >= 0.0
    
    # Shutdown
    pm.shutdown_all()
    stats = pm.get_plugin_lifecycle_stats()
    assert stats["test_plugin"]["state"] == "stopped"
    assert stats["test_plugin"]["shutdown_duration_ms"] >= 0.0


def test_heartbeat_scheduler_telemetry_reporting():
    """Verify HeartbeatScheduler runs loop and caches subsystem telemetry."""
    bus = InMemoryEventBus()
    pm = PluginManager()
    
    plugin = StubPlatformPlugin("test_plugin", "Test Plugin")
    pm.load(plugin)
    pm.initialize_all()
    
    hs = HeartbeatScheduler(event_bus=bus, plugin_manager=pm)
    
    # Telemetry emission
    hs._emit_heartbeats()
    
    # Verify cached telemetry
    hbs = hs.get_latest_heartbeats()
    assert "test_plugin" in hbs
    hb_data = hbs["test_plugin"]
    assert hb_data["module_id"] == "test_plugin"
    assert hb_data["module_name"] == "Test Plugin"
    assert hb_data["status"] == "running"
    assert hb_data["memory_usage"] > 0.0


def test_fastapi_platform_rest_endpoints():
    """Verify that new platform status, heartbeat, modules, and events endpoints return valid JSON."""
    container = Container()
    bus = InMemoryEventBus()
    pm = PluginManager()
    
    plugin = StubPlatformPlugin("test_plugin", "Test Plugin")
    pm.load(plugin)
    pm.initialize_all()
    
    hs = HeartbeatScheduler(event_bus=bus, plugin_manager=pm)
    hs._emit_heartbeats()
    
    # Register components in container
    container.register(InMemoryEventBus, instance=bus)
    container.register(IPluginManager, instance=pm)
    container.register("heartbeat_scheduler", instance=hs)
    
    # Dashboard components
    state_store = DashboardStateStore()
    repository = DashboardRepository()
    health_monitor = HealthMonitor()
    websocket_manager = WebSocketManager()
    orchestrator = DashboardOrchestrator()
    orchestrator.initialize(state_store, repository)
    event_aggregator = DashboardEventAggregator(
        orchestrator=orchestrator,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
    )
    
    app = create_app(
        state_store=state_store,
        repository=repository,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
        event_aggregator=event_aggregator,
        container=container,
    )
    
    client = TestClient(app)
    
    # 1. GET /platform/status
    res = client.get("/platform/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active"
    assert "test_plugin" in data["modules"]
    assert data["modules"]["test_plugin"]["state"] == "running"
    
    # 2. GET /platform/heartbeat
    res = client.get("/platform/heartbeat")
    assert res.status_code == 200
    data = res.json()
    assert "test_plugin" in data
    assert data["test_plugin"]["status"] == "running"
    
    # 3. GET /platform/modules
    res = client.get("/platform/modules")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "test_plugin"
    assert data[0]["name"] == "Test Plugin"
    
    # 4. GET /platform/events
    res = client.get("/platform/events")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
