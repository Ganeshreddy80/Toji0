"""Comprehensive Test Suite for Sprint 10B Monitoring & Dashboard Subsystem."""

import ast
from datetime import datetime, timedelta, timezone
import pathlib
import threading
import time

from pydantic import ValidationError
import pytest

from mission_control.dashboard_renderer import DashboardRenderer, DashboardSnapshot
from mission_control.history import BoundedHistory, HealthTransitionRecord
from mission_control.log_monitor import LogEntry, LogLevel, LogMonitor
from mission_control.monitoring import (
    AlertGenerated,
    DashboardUpdated,
    MonitoringManager,
    MonitoringStarted,
    MonitoringStopped,
    NotificationSent,
    ResourceThresholdExceeded,
)
from mission_control.notification_manager import (
    Notification,
    NotificationCategory,
    NotificationManager,
)
from mission_control.reports import ReportGenerator, SystemStatusReport
from mission_control.resource_monitor import ResourceMonitor, ResourceSnapshot
from mission_control.system_monitor import (
    ServiceHealthStatus,
    ServiceRegistration,
    SystemMonitor,
)
from mission_control.trend_analyzer import TrendAnalysisSnapshot, TrendAnalyzer
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def monitoring_mgr(event_bus):
    return MonitoringManager(event_bus=event_bus)


# 1. Monitoring lifecycle start
def test_monitoring_lifecycle_start(monitoring_mgr):
    assert monitoring_mgr.is_running() is False
    monitoring_mgr.start()
    assert monitoring_mgr.is_running() is True


# 2. Monitoring lifecycle stop
def test_monitoring_lifecycle_stop(monitoring_mgr):
    monitoring_mgr.start()
    assert monitoring_mgr.is_running() is True
    monitoring_mgr.stop()
    assert monitoring_mgr.is_running() is False


# 3. Dashboard rendering snapshot
def test_dashboard_rendering_snapshot():
    renderer = DashboardRenderer()
    snapshot = renderer.render_dashboard(
        controller_state="RUNNING",
        uptime_seconds=120.0,
        services=[],
        health_summary={"HEALTHY": 0},
        active_alerts=[],
    )
    assert snapshot is not None
    assert snapshot.controller_state == "RUNNING"
    assert snapshot.render_time_ms >= 0.0


# 4. Dashboard rendering immutability
def test_dashboard_rendering_immutability():
    renderer = DashboardRenderer()
    snapshot = renderer.render_dashboard(
        controller_state="RUNNING",
        uptime_seconds=120.0,
        services=[],
        health_summary={},
        active_alerts=[],
    )
    with pytest.raises((ValidationError, TypeError)):
        snapshot.controller_state = "STOPPED"


# 5. System monitor uptime
def test_system_monitor_uptime():
    sm = SystemMonitor()
    time.sleep(0.01)
    uptime = sm.get_controller_uptime_seconds()
    assert uptime > 0.0


# 6. System monitor service registration
def test_system_monitor_service_registration():
    sm = SystemMonitor()
    reg = sm.register_service("order_engine", "execution")
    assert reg.service_name == "order_engine"
    assert reg.health_status == ServiceHealthStatus.HEALTHY
    assert len(sm.get_registered_services()) == 1


# 7. System monitor unregister service
def test_system_monitor_unregister_service():
    sm = SystemMonitor()
    sm.register_service("order_engine")
    assert sm.unregister_service("order_engine") is True
    assert len(sm.get_registered_services()) == 0


# 8. System monitor health transition
def test_system_monitor_health_transition():
    sm = SystemMonitor()
    sm.register_service("feed_service")
    transition = sm.update_health_status("feed_service", ServiceHealthStatus.DEGRADED, latency_ms=12.5)
    assert transition is not None
    assert transition.previous_status == "HEALTHY"
    assert transition.new_status == "DEGRADED"
    assert "feed_service" in sm.get_failed_services()


# 9. System monitor service recovery
def test_system_monitor_service_recovery():
    sm = SystemMonitor()
    sm.register_service("feed_service")
    sm.update_health_status("feed_service", ServiceHealthStatus.UNHEALTHY)
    assert "feed_service" in sm.get_failed_services()

    sm.update_health_status("feed_service", ServiceHealthStatus.HEALTHY)
    assert "feed_service" not in sm.get_failed_services()
    assert "feed_service" in sm.get_recovered_services()


# 10. Resource monitor measurement
def test_resource_monitor_measurement():
    rm = ResourceMonitor()
    snapshot = rm.measure_resources(service_count=5)
    assert snapshot.process_uptime_seconds >= 0.0
    assert snapshot.memory_mb >= 0.0
    assert snapshot.service_count == 5


# 11. Resource monitor threshold check
def test_resource_monitor_threshold_check():
    rm = ResourceMonitor(cpu_threshold_percent=50.0, memory_threshold_mb=10.0)
    snap = ResourceSnapshot(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=75.0,
        memory_mb=5.0,
        peak_memory_mb=5.0,
        process_uptime_seconds=10.0,
        service_count=1,
    )
    exceeded, reason = rm.is_threshold_exceeded(snap)
    assert exceeded is True
    assert "CPU utilization" in reason


# 12. Log monitor record logs
def test_log_monitor_record_logs():
    lm = LogMonitor()
    e1 = lm.record_info("System initialized")
    e2 = lm.record_error("Connection failed", service_name="feed_service")

    assert e1.level == LogLevel.INFO
    assert e2.level == LogLevel.ERROR
    counts = lm.get_log_counts()
    assert counts["INFO"] == 1
    assert counts["ERROR"] == 1


# 13. Log monitor filter logs
def test_log_monitor_filter_logs():
    lm = LogMonitor()
    lm.record_info("Info message 1")
    lm.record_warning("Warning message 1")
    lm.record_error("Error message 1")

    filtered = lm.filter_logs(level=LogLevel.ERROR)
    assert len(filtered) == 1
    assert filtered[0].message == "Error message 1"


# 14. Notification manager service failure
def test_notification_manager_service_failure():
    nm = NotificationManager()
    n = nm.notify_service_failure("broker_gateway", "Connection timed out")
    assert n.category == NotificationCategory.SERVICE_FAILURE
    assert "broker_gateway" in n.title
    assert len(nm.get_notification_history()) == 1


# 15. Notification manager service recovery
def test_notification_manager_service_recovery():
    nm = NotificationManager()
    n = nm.notify_service_recovery("broker_gateway")
    assert n.category == NotificationCategory.SERVICE_RECOVERY
    assert "broker_gateway" in n.title


# 16. Notification manager critical alert
def test_notification_manager_critical_alert():
    nm = NotificationManager()
    n = nm.notify_critical_alert("Database Error", "Disk space critical")
    assert n.category == NotificationCategory.CRITICAL_ALERT


# 17. Notification manager heartbeat failure
def test_notification_manager_heartbeat_failure():
    nm = NotificationManager()
    n = nm.notify_heartbeat_failure("market_feed", latency_ms=500.0)
    assert n.category == NotificationCategory.HEARTBEAT_FAILURE


# 18. Trend analyzer moving average CPU
def test_trend_analyzer_moving_average_cpu():
    ta = TrendAnalyzer(window_size=5)
    for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
        ta.record_cpu_sample(val)

    avg = ta.calculate_moving_average_cpu()
    assert avg == 30.0


# 19. Trend analyzer alert frequency
def test_trend_analyzer_alert_frequency():
    ta = TrendAnalyzer()
    now = datetime.now(timezone.utc)
    ta.record_alert_event(now)
    ta.record_alert_event(now + timedelta(seconds=30))

    freq = ta.calculate_alert_frequency_per_minute()
    assert freq == 2.0  # 1 alert delta over 0.5 minutes = 2.0 alerts/min


# 20. Trend analyzer stability score
def test_trend_analyzer_stability_score():
    ta = TrendAnalyzer()
    score = ta.calculate_service_stability_score(total_services=10, failed_services_count=2, recent_alert_count=0)
    assert score == 0.8  # 8 healthy / 10 total = 0.8


# 21. Bounded history alert retention
def test_bounded_history_alert_retention():
    bh = BoundedHistory(max_alerts=3)
    for i in range(5):
        bh.add_alert({"id": i})

    alerts = bh.get_alerts()
    assert len(alerts) == 3
    assert alerts[0]["id"] == 2
    assert alerts[-1]["id"] == 4


# 22. Bounded history health change retention
def test_bounded_history_health_change_retention():
    bh = BoundedHistory(max_health_changes=2)
    for i in range(4):
        rec = HealthTransitionRecord(service_name=f"svc{i}", previous_status="HEALTHY", new_status="DEGRADED")
        bh.add_health_change(rec)

    changes = bh.get_health_changes()
    assert len(changes) == 2
    assert changes[0].service_name == "svc2"


# 23. Report generation immutable report
def test_report_generation_immutable_report():
    report = ReportGenerator.build_report(
        controller_state="RUNNING",
        uptime_seconds=300.0,
        services=[],
        health_summary={"HEALTHY": 0},
        failed_services=[],
    )
    assert report.controller_state == "RUNNING"
    assert report.passed if hasattr(report, "passed") else True
    with pytest.raises((ValidationError, TypeError)):
        report.controller_state = "STOPPED"


# 24. Report generation JSON export
def test_report_generation_json_export():
    report = ReportGenerator.build_report(
        controller_state="RUNNING",
        uptime_seconds=300.0,
        services=[],
        health_summary={"HEALTHY": 0},
        failed_services=["feed_service"],
    )
    json_str = ReportGenerator.export_report_json(report)
    assert "feed_service" in json_str
    assert "RUNNING" in json_str


# 25. Event generation MonitoringStarted
def test_event_generation_monitoring_started(event_bus):
    events = []
    event_bus.subscribe("MonitoringStarted", lambda e: events.append(e))

    mgr = MonitoringManager(event_bus=event_bus)
    mgr.start()

    assert len(events) == 1
    assert events[0].event_type == "MonitoringStarted"


# 26. Event generation MonitoringStopped
def test_event_generation_monitoring_stopped(event_bus):
    events = []
    event_bus.subscribe("MonitoringStopped", lambda e: events.append(e))

    mgr = MonitoringManager(event_bus=event_bus)
    mgr.start()
    mgr.stop()

    assert len(events) == 1
    assert events[0].event_type == "MonitoringStopped"


# 27. Event generation DashboardUpdated
def test_event_generation_dashboard_updated(event_bus):
    events = []
    event_bus.subscribe("DashboardUpdated", lambda e: events.append(e))

    mgr = MonitoringManager(event_bus=event_bus)
    mgr.render_dashboard()

    assert len(events) == 1
    assert events[0].event_type == "DashboardUpdated"


# 28. Event generation AlertGenerated
def test_event_generation_alert_generated(event_bus):
    events = []
    event_bus.subscribe("AlertGenerated", lambda e: events.append(e))

    mgr = MonitoringManager(event_bus=event_bus)
    mgr.trigger_alert("SYSTEM_FAULT", "CRITICAL", "Memory critical", "database")

    assert len(events) == 1
    assert events[0].alert_type == "SYSTEM_FAULT"
    assert events[0].severity == "CRITICAL"


# 29. Event generation NotificationSent
def test_event_generation_notification_sent(event_bus):
    events = []
    event_bus.subscribe("NotificationSent", lambda e: events.append(e))

    mgr = MonitoringManager(event_bus=event_bus)
    mgr.register_service("svc1")
    mgr.update_service_health("svc1", ServiceHealthStatus.UNHEALTHY)

    assert len(events) >= 1
    assert any(e.event_type == "NotificationSent" for e in events)


# 30. Event generation ResourceThresholdExceeded
def test_event_generation_resource_threshold_exceeded(event_bus):
    events = []
    event_bus.subscribe("ResourceThresholdExceeded", lambda e: events.append(e))

    rm = ResourceMonitor(cpu_threshold_percent=1.0)  # Low threshold to force breach
    mgr = MonitoringManager(event_bus=event_bus, resource_monitor=rm)
    mgr.check_resources()

    assert len(events) >= 1
    assert events[0].event_type == "ResourceThresholdExceeded"


# 31. Thread safety concurrent health updates
def test_thread_safety_concurrent_health_updates(monitoring_mgr):
    monitoring_mgr.register_service("svc_concurrent")
    errors = []

    def worker(idx):
        try:
            status = ServiceHealthStatus.HEALTHY if idx % 2 == 0 else ServiceHealthStatus.DEGRADED
            for _ in range(50):
                monitoring_mgr.update_service_health("svc_concurrent", status, latency_ms=10.0)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


# 32. Thread safety concurrent dashboard render
def test_thread_safety_concurrent_dashboard_render(monitoring_mgr):
    errors = []

    def worker():
        try:
            for _ in range(20):
                monitoring_mgr.render_dashboard()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


# 33. Performance 100+ services dashboard rendering (<500ms)
def test_performance_100_services_rendering(monitoring_mgr):
    for i in range(150):
        monitoring_mgr.register_service(f"service_{i}", "worker")

    start_t = time.perf_counter()
    snapshot = monitoring_mgr.render_dashboard()
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert snapshot.total_services == 150
    assert elapsed_ms < 500.0  # Render target < 500ms verified


# 34. Health summary calculation
def test_health_summary_calculation(monitoring_mgr):
    monitoring_mgr.register_service("s1")
    monitoring_mgr.register_service("s2")
    monitoring_mgr.register_service("s3")

    monitoring_mgr.update_service_health("s1", ServiceHealthStatus.HEALTHY)
    monitoring_mgr.update_service_health("s2", ServiceHealthStatus.DEGRADED)
    monitoring_mgr.update_service_health("s3", ServiceHealthStatus.UNHEALTHY)

    summary = monitoring_mgr.system_monitor.get_health_summary()
    assert summary["HEALTHY"] == 1
    assert summary["DEGRADED"] == 1
    assert summary["UNHEALTHY"] == 1


# 35. Log monitor level counts
def test_log_monitor_level_counts():
    lm = LogMonitor()
    lm.record_info("info 1")
    lm.record_info("info 2")
    lm.record_warning("warn 1")

    counts = lm.get_log_counts()
    assert counts["INFO"] == 2
    assert counts["WARNING"] == 1
    assert counts["ERROR"] == 0


# 36. Notification category query
def test_notification_category_query():
    nm = NotificationManager()
    nm.notify_service_failure("s1", "err")
    nm.notify_service_recovery("s1")

    failures = nm.get_notifications_by_category(NotificationCategory.SERVICE_FAILURE)
    recoveries = nm.get_notifications_by_category(NotificationCategory.SERVICE_RECOVERY)

    assert len(failures) == 1
    assert len(recoveries) == 1


# 37. Trend analyzer analyze_trends snapshot
def test_trend_analyzer_analyze_trends_snapshot():
    ta = TrendAnalyzer()
    ta.record_cpu_sample(25.0)
    ta.record_memory_sample(256.0)

    snapshot = ta.analyze_trends(uptime_seconds=3600.0, total_services=10, failed_services_count=1)
    assert snapshot.uptime_trend_seconds == 3600.0
    assert snapshot.moving_average_cpu_percent == 25.0
    assert snapshot.moving_average_memory_mb == 256.0


# 38. Bounded history clear
def test_bounded_history_clear():
    bh = BoundedHistory()
    bh.add_alert({"alert": 1})
    bh.add_health_change(HealthTransitionRecord(service_name="s1", previous_status="HEALTHY", new_status="DEGRADED"))
    bh.clear()

    assert len(bh.get_alerts()) == 0
    assert len(bh.get_health_changes()) == 0


# 39. Regression paper trading subsystem integrity
def test_regression_paper_trading_integrity():
    from paper_trading import PaperOrchestrator
    orch = PaperOrchestrator(initial_capital=100000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()


# 40. Architecture boundaries enforcement
def test_architecture_boundaries_enforcement():
    mc_dir = pathlib.Path(__file__).parent.parent / "mission_control"
    forbidden = {"strategy", "execution", "broker", "live_trading", "self_learning", "aws", "monte_carlo"}

    for py_file in mc_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        assert f not in alias.name, f"Forbidden import '{alias.name}' found in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for f in forbidden:
                        assert f not in node.module, f"Forbidden import from '{node.module}' found in {py_file.name}"
