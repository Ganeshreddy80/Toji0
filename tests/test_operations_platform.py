"""Comprehensive Test Suite — Sprint 12C Monitoring & Operations Platform (65 tests)."""

import ast
import pathlib
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from operations.alert_manager import AlertManager, AlertRecord, AlertStatus
from operations.alert_rules import AlertRule, AlertSeverity, ComparisonOperator
from operations.audit_logger import AuditEntry, AuditLogger
from operations.metrics_collector import MetricSnapshot, MetricsCollector
from operations.metrics_repository import MetricAggregate, MetricsRepository
from operations.operations_dashboard import DashboardView, OperationsDashboard
from operations.operations_events import (
    AlertAcknowledged,
    AlertResolved,
    AlertTriggered,
    AuditEntryCreated,
    DashboardGenerated,
    MetricsCollected,
    OperationsCycleCompleted,
    ReportGenerated,
)
from operations.operations_manager import OperationsManager
from operations.operations_reports import OperationsReport, OperationsReports, ReportType
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def ops_mgr(event_bus):
    return OperationsManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. Metrics Collector (Tests 1–5)
# ---------------------------------------------------------------------------
def test_collector_create_snapshot():
    collector = MetricsCollector()
    snap = collector.collect_snapshot("cpu_utilization", 45.5, "percent")
    assert snap.metric_name == "cpu_utilization"
    assert snap.value == 45.5
    assert snap.unit == "percent"
    assert snap.is_advisory_only is True


def test_collector_custom_labels():
    collector = MetricsCollector()
    snap = collector.collect_snapshot("latency", 15.0, "ms", labels={"node": "n1"})
    assert snap.labels["node"] == "n1"


def test_collector_system_metrics_batch():
    collector = MetricsCollector()
    batch = collector.collect_system_metrics(cpu_utilization=30.0, memory_utilization=50.0)
    assert len(batch) == 8
    names = {s.metric_name for s in batch}
    assert "cpu_utilization" in names
    assert "memory_utilization" in names


def test_collector_timestamp():
    collector = MetricsCollector()
    snap = collector.collect_snapshot("test", 1.0)
    assert snap.timestamp is not None


def test_collector_immutability():
    collector = MetricsCollector()
    snap = collector.collect_snapshot("m1", 10.0)
    with pytest.raises((ValidationError, TypeError)):
        snap.value = 20.0


# ---------------------------------------------------------------------------
# 2. Metrics Repository (Tests 6–12)
# ---------------------------------------------------------------------------
def test_repository_add_and_get():
    repo = MetricsRepository()
    snap = MetricSnapshot(metric_name="cpu", value=50.0)
    repo.add_snapshot(snap)

    results = repo.get_snapshots(metric_name="cpu")
    assert len(results) == 1
    assert results[0].value == 50.0


def test_repository_filtering_labels():
    repo = MetricsRepository()
    repo.add_snapshot(MetricSnapshot(metric_name="req", value=100.0, labels={"env": "prod"}))
    repo.add_snapshot(MetricSnapshot(metric_name="req", value=50.0, labels={"env": "dev"}))

    prod_snaps = repo.get_snapshots(metric_name="req", labels={"env": "prod"})
    assert len(prod_snaps) == 1
    assert prod_snaps[0].value == 100.0


def test_repository_aggregation():
    repo = MetricsRepository()
    repo.add_snapshot(MetricSnapshot(metric_name="temp", value=10.0))
    repo.add_snapshot(MetricSnapshot(metric_name="temp", value=20.0))
    repo.add_snapshot(MetricSnapshot(metric_name="temp", value=30.0))

    agg = repo.aggregate_metric("temp")
    assert agg is not None
    assert agg.count == 3
    assert agg.min_value == 10.0
    assert agg.max_value == 30.0
    assert agg.mean_value == 20.0


def test_repository_rolling_average():
    repo = MetricsRepository()
    repo.add_snapshot(MetricSnapshot(metric_name="load", value=2.0))
    repo.add_snapshot(MetricSnapshot(metric_name="load", value=4.0))

    avg = repo.calculate_rolling_average("load", window_seconds=60.0)
    assert avg == 3.0


def test_repository_time_window_query():
    repo = MetricsRepository()
    now = datetime.now(timezone.utc)
    s = MetricSnapshot(metric_name="m", value=1.0, timestamp=now)
    repo.add_snapshot(s)

    res = repo.time_window_query(now, now)
    assert len(res) == 1


def test_repository_bounded_eviction():
    repo = MetricsRepository(max_metrics=2)
    repo.add_snapshot(MetricSnapshot(metric_name="m1", value=1.0))
    repo.add_snapshot(MetricSnapshot(metric_name="m2", value=2.0))
    repo.add_snapshot(MetricSnapshot(metric_name="m3", value=3.0))

    assert repo.count() == 2
    snaps = repo.get_snapshots()
    assert snaps[0].metric_name == "m2"


def test_repository_clear():
    repo = MetricsRepository()
    repo.add_snapshot(MetricSnapshot(metric_name="m1", value=1.0))
    repo.clear()
    assert repo.count() == 0


# ---------------------------------------------------------------------------
# 3. Alert Rules (Tests 13–18)
# ---------------------------------------------------------------------------
def test_alert_rule_defaults():
    rule = AlertRule(rule_name="High CPU", metric_name="cpu_utilization", threshold_value=80.0)
    assert rule.comparison_operator == ComparisonOperator.GT
    assert rule.severity == AlertSeverity.WARNING
    assert rule.enabled is True
    assert rule.is_advisory_only is True


def test_alert_rule_operators():
    r_gt = AlertRule(rule_name="r", metric_name="m", comparison_operator=ComparisonOperator.GT, threshold_value=10.0)
    r_lt = AlertRule(rule_name="r", metric_name="m", comparison_operator=ComparisonOperator.LT, threshold_value=10.0)
    r_eq = AlertRule(rule_name="r", metric_name="m", comparison_operator=ComparisonOperator.EQ, threshold_value=10.0)

    assert r_gt.evaluate_value(15.0) is True
    assert r_gt.evaluate_value(5.0) is False

    assert r_lt.evaluate_value(5.0) is True
    assert r_lt.evaluate_value(15.0) is False

    assert r_eq.evaluate_value(10.0) is True
    assert r_eq.evaluate_value(10.1) is False


def test_alert_rule_disabled():
    rule = AlertRule(rule_name="r", metric_name="m", threshold_value=10.0, enabled=False)
    assert rule.evaluate_value(100.0) is False


def test_alert_rule_severity():
    rule = AlertRule(rule_name="r", metric_name="m", threshold_value=10.0, severity=AlertSeverity.CRITICAL)
    assert rule.severity == AlertSeverity.CRITICAL


def test_alert_rule_immutability():
    rule = AlertRule(rule_name="r", metric_name="m", threshold_value=10.0)
    with pytest.raises((ValidationError, TypeError)):
        rule.enabled = False


def test_alert_rule_advisory_flag():
    rule = AlertRule(rule_name="r", metric_name="m", threshold_value=10.0)
    assert rule.is_advisory_only is True


# ---------------------------------------------------------------------------
# 4. Alert Manager (Tests 19–25)
# ---------------------------------------------------------------------------
def test_alert_manager_register_rule():
    am = AlertManager()
    rule = am.register_rule("High Mem", "memory_utilization", threshold_value=85.0)
    assert rule.rule_name == "High Mem"
    assert am.get_rule(rule.rule_id) is not None


def test_alert_manager_evaluate_snapshot():
    am = AlertManager()
    am.register_rule("High CPU", "cpu_utilization", threshold_value=80.0)
    snap = MetricSnapshot(metric_name="cpu_utilization", value=90.0)

    triggered = am.evaluate_snapshot(snap)
    assert len(triggered) == 1
    assert triggered[0].rule_name == "High CPU"
    assert triggered[0].status == AlertStatus.ACTIVE


def test_alert_manager_evaluate_metrics_repo():
    am = AlertManager()
    repo = MetricsRepository()
    am.register_rule("High Disk", "disk_utilization", threshold_value=70.0)

    repo.add_snapshot(MetricSnapshot(metric_name="disk_utilization", value=75.0))
    alerts = am.evaluate_metrics(repo)

    assert len(alerts) == 1
    assert alerts[0].metric_name == "disk_utilization"


def test_alert_manager_acknowledge_alert():
    am = AlertManager()
    am.register_rule("r1", "m1", threshold_value=10.0)
    triggered = am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=20.0))

    alert_id = triggered[0].alert_id
    ack = am.acknowledge_alert(alert_id, acknowledged_by="sysadmin")

    assert ack.status == AlertStatus.ACKNOWLEDGED
    assert ack.acknowledged_by == "sysadmin"


def test_alert_manager_resolve_alert():
    am = AlertManager()
    am.register_rule("r1", "m1", threshold_value=10.0)
    triggered = am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=20.0))

    alert_id = triggered[0].alert_id
    resolved = am.resolve_alert(alert_id, resolution_note="Fixed memory leak")

    assert resolved.status == AlertStatus.RESOLVED
    assert resolved.resolution_note == "Fixed memory leak"


def test_alert_manager_active_vs_history():
    am = AlertManager()
    am.register_rule("r1", "m1", threshold_value=10.0)
    t = am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=20.0))

    assert len(am.get_active_alerts()) == 1
    am.resolve_alert(t[0].alert_id)

    assert len(am.get_active_alerts()) == 0
    assert len(am.get_alert_history()) == 1


def test_alert_manager_bounded_eviction():
    am = AlertManager(max_alerts=2)
    am.register_rule("r1", "m1", threshold_value=10.0)
    am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=20.0))
    am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=25.0))
    am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=30.0))

    assert am.count() == 2


# ---------------------------------------------------------------------------
# 5. Audit Logger (Tests 26–30)
# ---------------------------------------------------------------------------
def test_audit_logger_record_entry():
    logger = AuditLogger()
    entry = logger.record_entry("CONFIG_CHANGE", "service", "s1", actor="admin")
    assert entry.action == "CONFIG_CHANGE"
    assert entry.actor == "admin"
    assert entry.is_advisory_only is True


def test_audit_logger_filtering():
    logger = AuditLogger()
    logger.record_entry("DEPLOY", "service", "s1", actor="userA")
    logger.record_entry("APPROVE", "service", "s1", actor="userB")

    deploy_entries = logger.get_entries(action="DEPLOY")
    assert len(deploy_entries) == 1
    assert deploy_entries[0].actor == "userA"


def test_audit_logger_bounded_eviction():
    logger = AuditLogger(max_entries=2)
    logger.record_entry("a1", "r", "1")
    logger.record_entry("a2", "r", "2")
    logger.record_entry("a3", "r", "3")

    assert logger.count() == 2
    entries = logger.get_entries()
    assert entries[0].action == "a2"


def test_audit_logger_immutability():
    logger = AuditLogger()
    entry = logger.record_entry("a", "r", "1")
    with pytest.raises((ValidationError, TypeError)):
        entry.action = "MUTATED"


def test_audit_logger_no_filesystem_persistence():
    logger = AuditLogger()
    logger.record_entry("test", "res", "1")
    assert not hasattr(logger, "_file_path")
    assert not hasattr(logger, "save_to_disk")


# ---------------------------------------------------------------------------
# 6. Operations Dashboard (Tests 31–35)
# ---------------------------------------------------------------------------
def test_dashboard_generation():
    dash = OperationsDashboard()
    repo = MetricsRepository()
    am = AlertManager()
    al = AuditLogger()

    view = dash.generate_dashboard(repo, am, al)
    assert view.overall_status == "HEALTHY"
    assert view.is_advisory_only is True


def test_dashboard_metrics_summary():
    dash = OperationsDashboard()
    repo = MetricsRepository()
    repo.add_snapshot(MetricSnapshot(metric_name="cpu_utilization", value=50.0))
    am = AlertManager()
    al = AuditLogger()

    view = dash.generate_dashboard(repo, am, al)
    assert view.metrics_summary["cpu_mean_pct"] == 50.0


def test_dashboard_alert_summary():
    dash = OperationsDashboard()
    repo = MetricsRepository()
    am = AlertManager()
    al = AuditLogger()

    am.register_rule("r1", "m1", threshold_value=5.0, severity=AlertSeverity.CRITICAL)
    am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=10.0))

    view = dash.generate_dashboard(repo, am, al)
    assert view.alert_summary["active_alerts_count"] == 1
    assert view.alert_summary["has_critical_alerts"] is True
    assert view.overall_status == "DEGRADED"


def test_dashboard_integration_mock_health():
    class DummyHealthMonitor:
        def generate_health_report(self):
            return {"overall_status": "HEALTHY", "total_services": 5}

    dash = OperationsDashboard()
    repo = MetricsRepository()
    am = AlertManager()
    al = AuditLogger()

    view = dash.generate_dashboard(repo, am, al, health_monitor=DummyHealthMonitor())
    assert view.health_summary["total_services"] == 5


def test_dashboard_immutability():
    dash = OperationsDashboard()
    view = dash.generate_dashboard(MetricsRepository(), AlertManager(), AuditLogger())
    with pytest.raises((ValidationError, TypeError)):
        view.overall_status = "MUTATED"


# ---------------------------------------------------------------------------
# 7. Operations Reports (Tests 36–41)
# ---------------------------------------------------------------------------
def test_reports_operational_summary():
    reports = OperationsReports()
    rep = reports.generate_operational_summary(MetricsRepository(), AlertManager(), AuditLogger())
    assert rep.report_type == ReportType.SUMMARY
    assert "metrics" in rep.content


def test_reports_deployment_history():
    reports = OperationsReports()
    rep = reports.generate_deployment_history_report()
    assert rep.report_type == ReportType.DEPLOYMENT
    assert "total_deployments" in rep.content


def test_reports_alert_history():
    reports = OperationsReports()
    am = AlertManager()
    am.register_rule("r1", "m1", threshold_value=1.0)
    am.evaluate_snapshot(MetricSnapshot(metric_name="m1", value=2.0))

    rep = reports.generate_alert_history_report(am)
    assert rep.report_type == ReportType.ALERT
    assert rep.content["total_alerts"] == 1


def test_reports_health_overview():
    reports = OperationsReports()
    rep = reports.generate_health_overview_report()
    assert rep.report_type == ReportType.HEALTH


def test_reports_audit_overview():
    reports = OperationsReports()
    al = AuditLogger()
    al.record_entry("action", "type", "id")

    rep = reports.generate_audit_overview_report(al)
    assert rep.report_type == ReportType.AUDIT
    assert rep.content["total_entries"] == 1


def test_reports_immutability():
    reports = OperationsReports()
    rep = reports.generate_operational_summary(MetricsRepository(), AlertManager(), AuditLogger())
    with pytest.raises((ValidationError, TypeError)):
        rep.title = "New Title"


# ---------------------------------------------------------------------------
# 8. Operations Manager Lifecycle (Tests 42–48)
# ---------------------------------------------------------------------------
def test_ops_manager_collect_metrics(ops_mgr):
    snaps = ops_mgr.collect_metrics(cpu_utilization=40.0)
    assert len(snaps) == 8
    assert ops_mgr.metrics_repository.count() == 8


def test_ops_manager_evaluate_alerts(ops_mgr):
    ops_mgr.alert_manager.register_rule("High CPU", "cpu_utilization", threshold_value=50.0)
    ops_mgr.collect_metrics(cpu_utilization=60.0)

    active = ops_mgr.alert_manager.get_active_alerts()
    assert len(active) == 1


def test_ops_manager_acknowledge_alert(ops_mgr):
    ops_mgr.alert_manager.register_rule("r1", "cpu_utilization", threshold_value=10.0)
    ops_mgr.collect_metrics(cpu_utilization=20.0)

    alerts = ops_mgr.alert_manager.get_active_alerts()
    ack = ops_mgr.acknowledge_alert(alerts[0].alert_id, "op_user")
    assert ack.status == AlertStatus.ACKNOWLEDGED


def test_ops_manager_resolve_alert(ops_mgr):
    ops_mgr.alert_manager.register_rule("r1", "cpu_utilization", threshold_value=10.0)
    ops_mgr.collect_metrics(cpu_utilization=20.0)

    alerts = ops_mgr.alert_manager.get_active_alerts()
    res = ops_mgr.resolve_alert(alerts[0].alert_id, "Resolved naturally")
    assert res.status == AlertStatus.RESOLVED


def test_ops_manager_record_audit(ops_mgr):
    entry = ops_mgr.record_audit("TEST_ACTION", "system", "1")
    assert entry.action == "TEST_ACTION"
    assert ops_mgr.audit_logger.count() == 1


def test_ops_manager_generate_dashboard(ops_mgr):
    view = ops_mgr.generate_dashboard()
    assert view.overall_status == "HEALTHY"


def test_ops_manager_run_operations_cycle(ops_mgr):
    snaps, alerts, dash = ops_mgr.run_operations_cycle(cpu=10.0, mem=20.0)
    assert len(snaps) == 8
    assert dash.overall_status == "HEALTHY"


# ---------------------------------------------------------------------------
# 9. Events (Tests 49–56)
# ---------------------------------------------------------------------------
def test_event_metrics_collected(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("MetricsCollected", lambda e: evts.append(e))
    ops_mgr.collect_metrics()
    assert len(evts) == 1
    assert evts[0].event_type == "MetricsCollected"


def test_event_alert_triggered(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("AlertTriggered", lambda e: evts.append(e))
    ops_mgr.alert_manager.register_rule("High CPU", "cpu_utilization", threshold_value=50.0)
    ops_mgr.collect_metrics(cpu_utilization=60.0)
    assert len(evts) == 1
    assert evts[0].event_type == "AlertTriggered"


def test_event_alert_acknowledged(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("AlertAcknowledged", lambda e: evts.append(e))
    ops_mgr.alert_manager.register_rule("r1", "cpu_utilization", threshold_value=10.0)
    ops_mgr.collect_metrics(cpu_utilization=20.0)
    alerts = ops_mgr.alert_manager.get_active_alerts()

    ops_mgr.acknowledge_alert(alerts[0].alert_id)
    assert len(evts) == 1
    assert evts[0].event_type == "AlertAcknowledged"


def test_event_alert_resolved(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("AlertResolved", lambda e: evts.append(e))
    ops_mgr.alert_manager.register_rule("r1", "cpu_utilization", threshold_value=10.0)
    ops_mgr.collect_metrics(cpu_utilization=20.0)
    alerts = ops_mgr.alert_manager.get_active_alerts()

    ops_mgr.resolve_alert(alerts[0].alert_id)
    assert len(evts) == 1
    assert evts[0].event_type == "AlertResolved"


def test_event_audit_entry_created(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("AuditEntryCreated", lambda e: evts.append(e))
    ops_mgr.record_audit("ACTION", "res", "1")
    assert len(evts) == 1
    assert evts[0].event_type == "AuditEntryCreated"


def test_event_dashboard_generated(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("DashboardGenerated", lambda e: evts.append(e))
    ops_mgr.generate_dashboard()
    assert len(evts) == 1
    assert evts[0].event_type == "DashboardGenerated"


def test_event_report_generated(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("ReportGenerated", lambda e: evts.append(e))
    ops_mgr.generate_report(ReportType.SUMMARY)
    assert len(evts) == 1
    assert evts[0].event_type == "ReportGenerated"


def test_event_operations_cycle_completed(event_bus, ops_mgr):
    evts = []
    event_bus.subscribe("OperationsCycleCompleted", lambda e: evts.append(e))
    ops_mgr.run_operations_cycle()
    assert len(evts) == 1
    assert evts[0].event_type == "OperationsCycleCompleted"


# ---------------------------------------------------------------------------
# 10. Thread Safety & Concurrency (Tests 57–59)
# ---------------------------------------------------------------------------
def test_thread_safety_metrics_collection(ops_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(5):
                ops_mgr.collect_metrics(cpu_utilization=float(i * 10 + j))
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert ops_mgr.metrics_repository.count() == 200  # 5 threads * 5 loops * 8 metrics


def test_thread_safety_alert_management(ops_mgr):
    errors = []
    ops_mgr.alert_manager.register_rule("High CPU", "cpu_utilization", threshold_value=10.0)

    def worker(i):
        try:
            for j in range(5):
                snaps = ops_mgr.collect_metrics(cpu_utilization=20.0)
                alerts = ops_mgr.alert_manager.get_active_alerts()
                if alerts:
                    ops_mgr.acknowledge_alert(alerts[0].alert_id)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0


def test_thread_safety_audit_logging(ops_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(10):
                ops_mgr.record_audit(f"ACTION_{i}_{j}", "resource", str(j))
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert ops_mgr.audit_logger.count() == 50


# ---------------------------------------------------------------------------
# 11. Dependency Injection & Mockability (Tests 60–61)
# ---------------------------------------------------------------------------
def test_dependency_injection_metrics_repository():
    repo = MetricsRepository()
    mgr = OperationsManager(metrics_repository=repo)
    assert mgr.metrics_repository is repo


def test_dependency_injection_alert_manager():
    am = AlertManager()
    mgr = OperationsManager(alert_manager=am)
    assert mgr.alert_manager is am


# ---------------------------------------------------------------------------
# 12. Performance & Scale (Tests 62–63)
# ---------------------------------------------------------------------------
def test_performance_10000_metrics():
    repo = MetricsRepository(max_metrics=12000)
    collector = MetricsCollector()
    start_t = time.perf_counter()

    for i in range(10000):
        repo.add_snapshot(collector.collect_snapshot(f"m_{i}", float(i)))

    elapsed = time.perf_counter() - start_t
    assert repo.count() == 10000
    assert elapsed < 5.0  # Fast under capacity


def test_performance_5000_audit_entries():
    logger = AuditLogger(max_entries=6000)
    start_t = time.perf_counter()

    for i in range(5000):
        logger.record_entry("ACTION", "res", str(i))

    elapsed = time.perf_counter() - start_t
    assert logger.count() == 5000
    assert elapsed < 5.0  # Fast under capacity


# ---------------------------------------------------------------------------
# 13. Architecture Boundaries & Regression (Tests 64–65)
# ---------------------------------------------------------------------------
def test_regression_sprint12a_12b_unaffected():
    from deployment.deployment_manager import DeploymentManager
    from infrastructure.infrastructure_manager import InfrastructureManager

    infra = InfrastructureManager()
    dep = DeploymentManager()
    assert infra is not None
    assert dep is not None


def test_architecture_boundary_enforcement():
    ops_dir = pathlib.Path(__file__).parent.parent / "operations"
    forbidden = {
        "broker",
        "strategy",
        "execution",
        "live_trading",
        "paper_trading",
        "boto3",
        "docker",
        "prometheus_client",
        "opentelemetry",
    }

    violations = []
    for py_file in ops_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        if f in alias.name:
                            violations.append(f"Forbidden import '{alias.name}' in {py_file.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for f in forbidden:
                        if f in node.module:
                            violations.append(f"Forbidden from-import '{node.module}' in {py_file.name}")

    assert violations == [], f"Architecture violations found: {violations}"
