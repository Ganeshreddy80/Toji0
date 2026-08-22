import pytest
from dashboard.core.enums import HealthStatus
from dashboard.health.health_monitor import HealthMonitor


def test_health_monitor_initial_state() -> None:
    """Test that all default subsystems are registered as INITIALIZING."""
    monitor = HealthMonitor()
    health = monitor.get_health_status()

    assert len(health) == 8
    for sub in ["MIL", "PAE", "PQE", "CE", "SE", "TC", "RE", "PSE"]:
        assert sub in health
        assert health[sub].status == HealthStatus.INITIALIZING
        assert health[sub].message_count == 0
        assert health[sub].processing_latency_ms == 0.0


def test_health_monitor_register_message() -> None:
    """Test status transition and rolling latency calculations."""
    monitor = HealthMonitor()

    # Register first message
    monitor.register_message("MIL", 10.0)
    health = monitor.get_health_status()
    assert health["MIL"].status == HealthStatus.HEALTHY
    assert health["MIL"].message_count == 1
    assert health["MIL"].processing_latency_ms == 10.0

    # Register second message
    monitor.register_message("MIL", 20.0)
    health = monitor.get_health_status()
    assert health["MIL"].message_count == 2
    # Rolling average: (10 + 20) / 2 = 15.0
    assert health["MIL"].processing_latency_ms == 15.0


def test_health_monitor_manual_override() -> None:
    """Test manual state override overrides initialization state but error states persist."""
    monitor = HealthMonitor()

    # Explicit override to warning
    monitor.set_status("PAE", HealthStatus.WARNING)
    health = monitor.get_health_status()
    assert health["PAE"].status == HealthStatus.WARNING

    # Explicit override to error
    monitor.set_status("PAE", HealthStatus.ERROR)
    health = monitor.get_health_status()
    assert health["PAE"].status == HealthStatus.ERROR

    # Ingestion during error keeps error status
    monitor.register_message("PAE", 5.0)
    health = monitor.get_health_status()
    assert health["PAE"].status == HealthStatus.ERROR
    assert health["PAE"].message_count == 1


def test_health_monitor_dynamic_registration() -> None:
    """Test that an unknown subsystem is dynamically registered as healthy."""
    monitor = HealthMonitor()
    assert "UNKNOWN_SUB" not in monitor.get_health_status()

    monitor.register_message("UNKNOWN_SUB", 8.0)
    health = monitor.get_health_status()
    assert "UNKNOWN_SUB" in health
    assert health["UNKNOWN_SUB"].status == HealthStatus.HEALTHY
    assert health["UNKNOWN_SUB"].message_count == 1
    assert health["UNKNOWN_SUB"].processing_latency_ms == 8.0
