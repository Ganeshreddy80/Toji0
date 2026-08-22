import pytest
from datetime import datetime, timezone, timedelta
from toji_platform.services.alert_manager import AlertManager, AlertLevel

class MockHealthMonitor:
    def __init__(self):
        self.report = {
            "kernel_state": "running",
            "plugin_states": {"market_gateway": "running"},
            "uptime_seconds": 100.0,
            "restart_count": 0,
            "exception_count": 0,
            "active_thread_count": 10,
            "memory_usage_mb": 150.0,
            "cpu_usage_percent": 5.0,
            "lifecycle_status": {"Runtime Health Monitor": "running"},
            "heartbeat_status": {
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "healthy": True
            },
            "event_bus_health": {
                "listener_count": 5,
                "publish_failures": 0,
                "healthy": True
            }
        }

    def get_health_report(self):
        return self.report

def test_alert_manager_happy_path():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)
    alerts = manager.evaluate_rules()
    assert len(alerts) == 0

def test_alert_manager_memory_thresholds():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # 1. Warning threshold
    monitor.report["memory_usage_mb"] = 600.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "memory_usage"
    assert alerts[0].level == AlertLevel.WARNING

    # 2. Error threshold
    monitor.report["memory_usage_mb"] = 850.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.ERROR

    # 3. Critical threshold
    monitor.report["memory_usage_mb"] = 1100.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_cpu_thresholds():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # 1. Warning threshold
    monitor.report["cpu_usage_percent"] = 85.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "cpu_usage"
    assert alerts[0].level == AlertLevel.WARNING

    # 2. Error threshold
    monitor.report["cpu_usage_percent"] = 92.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.ERROR

    # 3. Critical threshold
    monitor.report["cpu_usage_percent"] = 97.0
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_heartbeat_timeout():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # 1. Heartbeat never received
    monitor.report["heartbeat_status"]["last_heartbeat"] = None
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "heartbeat_timeout"
    assert alerts[0].level == AlertLevel.WARNING

    # 2. Error timeout (6s elapsed)
    six_seconds_ago = datetime.now(timezone.utc) - timedelta(seconds=6)
    monitor.report["heartbeat_status"]["last_heartbeat"] = six_seconds_ago.isoformat()
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.ERROR

    # 3. Critical timeout (11s elapsed)
    eleven_seconds_ago = datetime.now(timezone.utc) - timedelta(seconds=11)
    monitor.report["heartbeat_status"]["last_heartbeat"] = eleven_seconds_ago.isoformat()
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_exceptions():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # 1. Warning (2 exceptions)
    monitor.report["exception_count"] = 2
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "exception_rate"
    assert alerts[0].level == AlertLevel.WARNING

    # 2. Error (6 exceptions)
    monitor.report["exception_count"] = 6
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.ERROR

    # 3. Critical (12 exceptions)
    monitor.report["exception_count"] = 12
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_restarts():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # 1. Warning (1 restart)
    monitor.report["restart_count"] = 1
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "restart_frequency"
    assert alerts[0].level == AlertLevel.WARNING

    # 2. Error (3 restarts)
    monitor.report["restart_count"] = 3
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.ERROR

    # 3. Critical (6 restarts)
    monitor.report["restart_count"] = 6
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_plugin_failures():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # Plugin fails
    monitor.report["plugin_states"]["risk_engine"] = "failed"
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "plugin_failure"
    assert alerts[0].level == AlertLevel.CRITICAL

def test_alert_manager_event_bus_failures():
    monitor = MockHealthMonitor()
    manager = AlertManager(monitor)

    # Event bus publishes failures
    monitor.report["event_bus_health"]["publish_failures"] = 1
    alerts = manager.evaluate_rules()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "event_bus_failure"
    assert alerts[0].level == AlertLevel.ERROR
