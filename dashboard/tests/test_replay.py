import pytest
from dashboard.core.enums import HealthStatus
from dashboard.health.health_monitor import HealthMonitor


def test_replay_status_transitions() -> None:
    """Test that health monitor tracks and preserves replay status transitions."""
    monitor = HealthMonitor()
    
    # 1. Defaults to LIVE
    health = monitor.get_health_status()
    for sub in ["MIL", "PAE", "PQE"]:
        assert health[sub].replay_status == "LIVE"

    # 2. Set MIL to REPLAYING
    monitor.set_status("MIL", HealthStatus.HEALTHY, replay_status="REPLAYING")
    health = monitor.get_health_status()
    assert health["MIL"].replay_status == "REPLAYING"
    assert health["MIL"].status == HealthStatus.HEALTHY

    # 3. Message registrations preserve active replay_status state
    monitor.register_message("MIL", 5.0)
    health = monitor.get_health_status()
    assert health["MIL"].replay_status == "REPLAYING"
    assert health["MIL"].message_count == 1

    # 4. Unknown/Dynamic registers as LIVE initially
    monitor.register_message("CUSTOM_RUN", 12.0)
    health = monitor.get_health_status()
    assert health["CUSTOM_RUN"].replay_status == "LIVE"
