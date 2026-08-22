"""Comprehensive Test Suite for Sprint 10C Operational Automation Subsystem."""

import ast
from datetime import datetime, timedelta, timezone
import pathlib
import threading
import time

from pydantic import ValidationError
import pytest

from mission_control.audit_log import AuditLog, AuditLogEntry
from mission_control.automation import (
    AutomationDisabled,
    AutomationEnabled,
    AutomationManager,
    DependencyFailure,
    EscalationRaised,
    MaintenanceEnded,
    MaintenanceStarted,
    RecoveryCompleted,
    RecoveryStarted,
    RestartPerformed,
)
from mission_control.automation_metrics import AutomationMetricsCollector, AutomationMetricsSnapshot
from mission_control.dependency_manager import DependencyManager, DependencyNode
from mission_control.escalation_manager import (
    EscalationLevel,
    EscalationManager,
    EscalationReason,
    EscalationRecord,
)
from mission_control.maintenance_scheduler import MaintenanceScheduler, MaintenanceState, MaintenanceWindow
from mission_control.policies import (
    AutoRestartPolicy,
    EscalationPolicy,
    MaintenancePolicy,
    RecoveryPolicy,
)
from mission_control.recovery_engine import RecoveryAttemptRecord, RecoveryEngine, RecoveryType
from mission_control.restart_manager import RestartManager, RestartRecord
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def automation_mgr(event_bus):
    return AutomationManager(event_bus=event_bus)


# 1. Automation lifecycle enable
def test_automation_lifecycle_enable(automation_mgr):
    automation_mgr.disable()
    assert automation_mgr.is_enabled() is False
    automation_mgr.enable()
    assert automation_mgr.is_enabled() is True


# 2. Automation lifecycle disable
def test_automation_lifecycle_disable(automation_mgr):
    assert automation_mgr.is_enabled() is True
    automation_mgr.disable()
    assert automation_mgr.is_enabled() is False


# 3. Recovery engine service recovery
def test_recovery_engine_service_recovery():
    engine = RecoveryEngine()
    success, record, msg = engine.execute_service_recovery("order_service", "Process crashed")
    assert success is True
    assert record.service_name == "order_service"
    assert record.attempt_number == 1
    assert record.recovery_type == RecoveryType.SERVICE_RECOVERY


# 4. Recovery engine heartbeat recovery
def test_recovery_engine_heartbeat_recovery():
    engine = RecoveryEngine()
    success, record, msg = engine.execute_heartbeat_recovery("market_feed", latency_ms=650.0)
    assert success is True
    assert record.recovery_type == RecoveryType.HEARTBEAT_RECOVERY
    assert "650.0" in record.message


# 5. Recovery engine degraded recovery
def test_recovery_engine_degraded_recovery():
    engine = RecoveryEngine()
    success, record, msg = engine.execute_degraded_recovery("analytics_svc", "High queue backlog")
    assert success is True
    assert record.recovery_type == RecoveryType.DEGRADED_RECOVERY


# 6. Recovery engine repeated failure recovery
def test_recovery_engine_repeated_failure_recovery():
    engine = RecoveryEngine()
    success, record, msg = engine.execute_repeated_failure_recovery("auth_gateway", failure_count=4)
    assert success is True
    assert record.recovery_type == RecoveryType.REPEATED_FAILURE_RECOVERY


# 7. Recovery engine retry limit enforcement
def test_recovery_engine_retry_limit():
    policy = RecoveryPolicy(max_retries=2)
    engine = RecoveryEngine(policy=policy)

    s1, r1, _ = engine.execute_service_recovery("svc1", "err1")
    s2, r2, _ = engine.execute_service_recovery("svc1", "err2")
    s3, r3, msg3 = engine.execute_service_recovery("svc1", "err3")

    assert s1 is True
    assert s2 is True
    assert s3 is False
    assert "exhausted" in msg3


# 8. Restart manager auto restart
def test_restart_manager_auto_restart():
    rm = RestartManager()
    success, record, msg = rm.request_restart("data_feed", "Unresponsive socket")
    assert success is True
    assert record.service_name == "data_feed"
    assert record.is_manual is False


# 9. Restart manager force restart
def test_restart_manager_force_restart():
    rm = RestartManager()
    record = rm.force_restart("data_feed", reason="Scheduled upgrade", operator="ADMIN")
    assert record.is_manual is True
    assert record.operator == "ADMIN"


# 10. Restart manager loop prevention limit
def test_restart_manager_loop_prevention():
    policy = AutoRestartPolicy(max_restarts=2, window_seconds=600.0)
    rm = RestartManager(policy=policy)

    ok1, _, _ = rm.request_restart("flapping_svc", "crash 1")
    ok2, _, _ = rm.request_restart("flapping_svc", "crash 2")
    ok3, _, msg3 = rm.request_restart("flapping_svc", "crash 3")

    assert ok1 is True
    assert ok2 is True
    assert ok3 is False
    assert "limit exceeded" in msg3


# 11. Maintenance scheduler schedule maintenance
def test_maintenance_scheduler_schedule():
    ms = MaintenanceScheduler()
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=2)
    window = ms.schedule_maintenance("db_service", start, end, "Database index optimization")

    assert window.service_name == "db_service"
    assert window.state == MaintenanceState.SCHEDULED


# 12. Maintenance scheduler start and end window
def test_maintenance_scheduler_lifecycle():
    ms = MaintenanceScheduler()
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    w = ms.schedule_maintenance("svc_maint", start, end, "Routine check")

    active_w = ms.start_maintenance(w.window_id)
    assert active_w.state == MaintenanceState.ACTIVE
    assert ms.is_in_maintenance("svc_maint") is True

    completed_w = ms.end_maintenance(w.window_id)
    assert completed_w.state == MaintenanceState.COMPLETED
    assert ms.is_in_maintenance("svc_maint") is False


# 13. Dependency manager add dependency
def test_dependency_manager_add_dependency():
    dm = DependencyManager()
    ok = dm.add_dependency("web_gateway", "auth_service")
    assert ok is True
    assert "auth_service" in dm.get_dependencies("web_gateway")
    assert "web_gateway" in dm.get_dependents("auth_service")


# 14. Dependency manager cycle prevention
def test_dependency_manager_cycle_prevention():
    dm = DependencyManager()
    dm.add_dependency("svc_a", "svc_b")
    dm.add_dependency("svc_b", "svc_c")

    # Attempting to add svc_c -> svc_a creates cycle (svc_a -> svc_b -> svc_c -> svc_a)
    ok = dm.add_dependency("svc_c", "svc_a")
    assert ok is False


# 15. Dependency manager failure impact propagation
def test_dependency_manager_failure_impact():
    dm = DependencyManager()
    dm.add_dependency("order_api", "db_primary")
    dm.add_dependency("risk_checker", "order_api")

    impacted = dm.record_service_failure("db_primary")
    assert "order_api" in impacted
    assert "risk_checker" in impacted


# 16. Escalation manager raise escalation
def test_escalation_manager_raise():
    em = EscalationManager()
    record = em.raise_escalation(
        "payment_gw",
        EscalationLevel.CRITICAL,
        EscalationReason.RECOVERY_EXHAUSTION,
        "Recovery retries exhausted",
    )
    assert record.level == EscalationLevel.CRITICAL
    assert len(em.get_active_escalations()) == 1


# 17. Escalation manager escalation helpers
def test_escalation_manager_helpers():
    em = EscalationManager()
    r1 = em.escalate_restart_limit_exceeded("flapping_node", 5)
    r2 = em.escalate_dependency_failure("downstream_node", ["upstream_node"])

    assert r1.reason == EscalationReason.RESTART_LIMIT_EXCEEDED
    assert r2.reason == EscalationReason.DEPENDENCY_FAILURE


# 18. Audit log recording
def test_audit_log_recording():
    audit = AuditLog()
    e = audit.record("RESTART", "cache_service", "SUCCESS", "Memory clean", operator="MONITOR")
    assert e.action == "RESTART"
    assert e.outcome == "SUCCESS"
    assert e.operator == "MONITOR"
    assert len(audit.get_entries()) == 1


# 19. Audit log immutability
def test_audit_log_immutability():
    audit = AuditLog()
    e = audit.record("RECOVERY", "svc1", "SUCCESS", "ok")
    with pytest.raises((ValidationError, TypeError)):
        e.action = "MODIFY"


# 20. Automation metrics snapshot
def test_automation_metrics_snapshot():
    collector = AutomationMetricsCollector()
    collector.record_recovery_attempt()
    collector.record_recovery_success()
    collector.record_restart()
    collector.record_escalation()

    snap = collector.get_snapshot()
    assert snap.recovery_count == 1
    assert snap.successful_recoveries_count == 1
    assert snap.restart_count == 1
    assert snap.escalations_count == 1


# 21. Policy execution policy update
def test_policy_execution_update(automation_mgr):
    new_restart_policy = AutoRestartPolicy(max_restarts=5, window_seconds=1800.0)
    ok = automation_mgr.execute_policy(new_restart_policy, "global")

    assert ok is True
    assert automation_mgr.restart_manager._policy.max_restarts == 5


# 22. Event publication AutomationEnabled
def test_event_automation_enabled(event_bus):
    events = []
    event_bus.subscribe("AutomationEnabled", lambda e: events.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    mgr.disable()
    mgr.enable()

    assert len(events) == 1
    assert events[0].event_type == "AutomationEnabled"


# 23. Event publication AutomationDisabled
def test_event_automation_disabled(event_bus):
    events = []
    event_bus.subscribe("AutomationDisabled", lambda e: events.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    mgr.disable()

    assert len(events) == 1
    assert events[0].event_type == "AutomationDisabled"


# 24. Event publication RecoveryStarted & RecoveryCompleted
def test_event_recovery_events(event_bus):
    started_evts = []
    completed_evts = []
    event_bus.subscribe("RecoveryStarted", lambda e: started_evts.append(e))
    event_bus.subscribe("RecoveryCompleted", lambda e: completed_evts.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    mgr.execute_recovery("feed_engine", "SERVICE_RECOVERY", "Socket crash")

    assert len(started_evts) == 1
    assert len(completed_evts) == 1
    assert started_evts[0].service_name == "feed_engine"
    assert completed_evts[0].success is True


# 25. Event publication RestartPerformed
def test_event_restart_performed(event_bus):
    events = []
    event_bus.subscribe("RestartPerformed", lambda e: events.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    mgr.execute_recovery("feed_engine", "SERVICE_RECOVERY", "Socket crash")

    assert len(events) == 1
    assert events[0].service_name == "feed_engine"


# 26. Event publication MaintenanceStarted & MaintenanceEnded
def test_event_maintenance_events(event_bus):
    started_evts = []
    ended_evts = []
    event_bus.subscribe("MaintenanceStarted", lambda e: started_evts.append(e))
    event_bus.subscribe("MaintenanceEnded", lambda e: ended_evts.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    window = mgr.start_maintenance_window("db_node", start, end, "Patching")
    mgr.end_maintenance_window(window.window_id)

    assert len(started_evts) == 1
    assert len(ended_evts) == 1


# 27. Event publication DependencyFailure
def test_event_dependency_failure(event_bus):
    events = []
    event_bus.subscribe("DependencyFailure", lambda e: events.append(e))

    mgr = AutomationManager(event_bus=event_bus)
    mgr.dependency_manager.add_dependency("api_server", "core_db")
    mgr.handle_service_failure("core_db", "Disk error")

    assert len(events) == 1
    assert events[0].failed_service == "core_db"
    assert "api_server" in events[0].impacted_services


# 28. Event publication EscalationRaised
def test_event_escalation_raised(event_bus):
    events = []
    event_bus.subscribe("EscalationRaised", lambda e: events.append(e))

    policy = RecoveryPolicy(max_retries=1)
    engine = RecoveryEngine(policy=policy)
    mgr = AutomationManager(event_bus=event_bus, recovery_engine=engine)

    # Exhaust retries to trigger escalation event
    mgr.execute_recovery("flapping_svc", "SERVICE_RECOVERY", "err1")
    mgr.execute_recovery("flapping_svc", "SERVICE_RECOVERY", "err2")

    assert len(events) >= 1
    assert events[0].service_name == "flapping_svc"


# 29. Thread safety concurrent recovery requests
def test_thread_safety_concurrent_recovery(automation_mgr):
    errors = []

    def worker(i):
        try:
            for _ in range(20):
                automation_mgr.execute_recovery(f"svc_{i % 3}", "SERVICE_RECOVERY", "test")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


# 30. Thread safety concurrent dependency graph updates
def test_thread_safety_concurrent_dependency_updates():
    dm = DependencyManager()
    errors = []

    def worker(i):
        try:
            for j in range(20):
                dm.add_dependency(f"svc_{i}_{j}", "root_svc")
                dm.record_service_failure("root_svc")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


# 31. Performance 100+ services recovery decision (<100ms)
def test_performance_recovery_decision(automation_mgr):
    for i in range(150):
        automation_mgr.dependency_manager.add_dependency(f"svc_{i}", "core_bus")

    start_t = time.perf_counter()
    can, _ = automation_mgr.recovery_engine.can_attempt_recovery("svc_100")
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert can is True
    assert elapsed_ms < 100.0  # SLA < 100ms decision verified


# 32. Performance 100+ nodes dependency graph traversal (<100ms)
def test_performance_dependency_traversal():
    dm = DependencyManager()
    # Chain of 150 services
    for i in range(150):
        dm.add_dependency(f"node_{i+1}", f"node_{i}")

    start_t = time.perf_counter()
    impacted = dm.record_service_failure("node_0")
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert len(impacted) == 150
    assert elapsed_ms < 100.0  # SLA < 100ms traversal verified


# 33. Maintenance window recovery suppression
def test_maintenance_window_recovery_suppression(automation_mgr):
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    automation_mgr.start_maintenance_window("maint_svc", start, end, "Upgrading")

    # Recovery should be skipped during active maintenance
    success, rec, msg = automation_mgr.execute_recovery("maint_svc", "SERVICE_RECOVERY", "Unresponsive")
    assert success is False
    assert rec is None
    assert "maintenance" in msg


# 34. Audit log query filtering
def test_audit_log_query_filtering():
    audit = AuditLog()
    audit.record("RESTART", "svc_a", "SUCCESS", "ok")
    audit.record("RECOVERY", "svc_b", "SUCCESS", "ok")
    audit.record("RESTART", "svc_b", "FAILED", "err")

    filtered = audit.get_entries(service="svc_b", action="RESTART")
    assert len(filtered) == 1
    assert filtered[0].service == "svc_b"
    assert filtered[0].action == "RESTART"


# 35. Maintenance scheduler is_in_maintenance check
def test_maintenance_is_in_maintenance():
    ms = MaintenanceScheduler()
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=10)
    end = now + timedelta(minutes=50)

    ms.schedule_maintenance("svc_now", start, end, "Current maintenance")
    assert ms.is_in_maintenance("svc_now", now=now) is True


# 36. Escalation resolve escalation
def test_escalation_resolve():
    em = EscalationManager()
    em.escalate_repeated_failures("failing_svc", 4)
    assert len(em.get_active_escalations()) == 1

    ok = em.resolve_escalation("failing_svc")
    assert ok is True
    assert len(em.get_active_escalations()) == 0


# 37. Bounded audit log retention
def test_bounded_audit_log_retention():
    audit = AuditLog(max_entries=3)
    for i in range(5):
        audit.record("ACTION", "svc", "SUCCESS", f"reason {i}")

    entries = audit.get_entries()
    assert len(entries) == 3
    assert "reason 2" in entries[0].reason
    assert "reason 4" in entries[-1].reason


# 38. Bounded restart history retention
def test_bounded_restart_history_retention():
    rm = RestartManager(max_history=2)
    rm.force_restart("s1", "r1")
    rm.force_restart("s2", "r2")
    rm.force_restart("s3", "r3")

    history = rm.get_restart_history()
    assert len(history) == 2
    assert history[0].service_name == "s2"


# 39. Regression paper trading integrity
def test_regression_paper_trading_integrity():
    from paper_trading import PaperOrchestrator
    orch = PaperOrchestrator(initial_capital=100000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()


# 40. Architecture boundaries enforcement
def test_architecture_boundaries_enforcement():
    mc_dir = pathlib.Path(__file__).parent.parent / "mission_control"
    forbidden = {"strategy", "broker", "execution", "live_trading", "self_learning", "aws", "monte_carlo"}

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
