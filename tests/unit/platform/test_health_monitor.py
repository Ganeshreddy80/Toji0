import time
import pytest
from toji_platform.kernel import TojiKernel
from toji_platform.core.types import HealthStatus
from toji_platform.services.health_monitor import RuntimeHealthMonitor
from toji_platform.core.event_bus.interfaces import IEvent

class SimpleEvent:
    def __init__(self, event_type: str):
        self.event_type = event_type
        self.payload = {}
        self.event_id = "test-id"
        self.source = "test-source"

def test_health_monitor_metrics():
    kernel = TojiKernel()

    # Kernel starts stopped
    assert kernel.health_monitor.check_health() == HealthStatus.UNHEALTHY

    kernel.boot()

    # After boot, monitor is running
    assert kernel.health_monitor.check_health() == HealthStatus.HEALTHY

    report = kernel.health_monitor.get_health_report()

    assert report["kernel_state"] == "running"
    assert report["restart_count"] == 0
    assert report["exception_count"] == 0
    assert report["active_thread_count"] > 0
    assert report["memory_usage_mb"] > 0
    assert report["cpu_usage_percent"] >= 0.0
    assert "Runtime Health Monitor" in report["lifecycle_status"]
    assert report["lifecycle_status"]["Runtime Health Monitor"] == "running"
    assert report["heartbeat_status"]["healthy"] is False  # No heartbeat yet

    # Publish a heartbeat
    event = SimpleEvent("system.heartbeat")
    kernel.event_bus.publish(event)

    # Heartbeat should now be tracked
    report2 = kernel.health_monitor.get_health_report()
    assert report2["heartbeat_status"]["healthy"] is True
    assert report2["heartbeat_status"]["last_heartbeat"] is not None

    # Test event bus failure tracking
    def failing_handler(evt):
        raise ValueError("failing handler")

    kernel.event_bus.subscribe("test.fail", failing_handler)

    from toji_platform.core.errors import EventBusError
    with pytest.raises(EventBusError):
        kernel.event_bus.publish(SimpleEvent("test.fail"))

    report3 = kernel.health_monitor.get_health_report()
    assert report3["exception_count"] == 1
    assert report3["event_bus_health"]["publish_failures"] == 1
    assert report3["event_bus_health"]["healthy"] is False

    # Test restart count tracking
    kernel.restart()
    report4 = kernel.health_monitor.get_health_report()
    assert report4["restart_count"] == 1

    kernel.shutdown()
    assert kernel.health_monitor.check_health() == HealthStatus.UNHEALTHY
