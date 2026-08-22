"""Comprehensive Test Suite — Sprint 12B Container & Deployment Platform (60 tests)."""

import ast
import pathlib
import threading
import time
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from deployment.container_runtime import ContainerInfo, ContainerState, MockContainerRuntime
from deployment.deployment_config import DeploymentConfig, DeploymentEnvironment, DeploymentStrategy
from deployment.deployment_descriptor import DeploymentDescriptor, DeploymentStatus
from deployment.deployment_events import (
    DeploymentApproved,
    DeploymentArchived,
    DeploymentCancelled,
    DeploymentCreated,
    DeploymentValidated,
    HealthStatusUpdated,
    RuntimeOperationPerformed,
    ServiceRegistered,
)
from deployment.deployment_manager import DeploymentManager
from deployment.deployment_planner import DeploymentPlan, DeploymentPlanner
from deployment.deployment_validator import DeploymentValidator, ValidationReport
from deployment.health_monitor import HealthMonitor, ServiceHealthRecord
from deployment.service_registry import ServiceRecord, ServiceRegistry
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def dep_mgr(event_bus):
    return DeploymentManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. Deployment Configuration (Tests 1–5)
# ---------------------------------------------------------------------------
def test_config_defaults():
    cfg = DeploymentConfig()
    assert cfg.environment == DeploymentEnvironment.DEV
    assert cfg.cpu_allocation == 1.0
    assert cfg.memory_allocation_mb == 512
    assert cfg.replica_count == 1
    assert cfg.deployment_strategy == DeploymentStrategy.ROLLING
    assert cfg.is_advisory_only is True


def test_config_custom_values():
    cfg = DeploymentConfig(
        environment=DeploymentEnvironment.PROD,
        cpu_allocation=2.0,
        memory_allocation_mb=1024,
        replica_count=3,
        deployment_strategy=DeploymentStrategy.BLUE_GREEN,
    )
    assert cfg.environment == DeploymentEnvironment.PROD
    assert cfg.cpu_allocation == 2.0
    assert cfg.replica_count == 3
    assert cfg.deployment_strategy == DeploymentStrategy.BLUE_GREEN


def test_config_invalid_cpu():
    with pytest.raises(ValidationError):
        DeploymentConfig(cpu_allocation=-1.0)


def test_config_invalid_memory():
    with pytest.raises(ValidationError):
        DeploymentConfig(memory_allocation_mb=10)


def test_config_immutability():
    cfg = DeploymentConfig()
    with pytest.raises((ValidationError, TypeError)):
        cfg.replica_count = 5


# ---------------------------------------------------------------------------
# 2. Deployment Descriptor (Tests 6–10)
# ---------------------------------------------------------------------------
def test_descriptor_creation():
    desc = DeploymentDescriptor(service_name="auth-service", version="2.0.0")
    assert desc.service_name == "auth-service"
    assert desc.version == "2.0.0"
    assert desc.status == DeploymentStatus.CREATED
    assert desc.is_advisory_only is True


def test_descriptor_status_transitions():
    desc = DeploymentDescriptor(service_name="svc1")
    assert desc.status == DeploymentStatus.CREATED


def test_descriptor_advisory_flag():
    desc = DeploymentDescriptor(service_name="svc2")
    assert desc.is_advisory_only is True


def test_descriptor_immutability():
    desc = DeploymentDescriptor(service_name="svc3")
    with pytest.raises((ValidationError, TypeError)):
        desc.status = DeploymentStatus.APPROVED


def test_descriptor_error_message():
    desc = DeploymentDescriptor(service_name="svc4", error_message="Validation error")
    assert desc.error_message == "Validation error"


# ---------------------------------------------------------------------------
# 3. Service Registry & Dependency Graph (Tests 11–16)
# ---------------------------------------------------------------------------
def test_registry_register_and_get():
    reg = ServiceRegistry()
    rec = reg.register_service("api-gateway", version="1.1.0", dependencies=["auth-service"])
    assert rec.service_name == "api-gateway"
    assert rec.dependencies == ["auth-service"]
    assert reg.get_service("api-gateway") is not None


def test_registry_version_history():
    reg = ServiceRegistry()
    reg.register_service("order-service", version="1.0.0")
    reg.register_service("order-service", version="1.1.0")

    hist = reg.get_version_history("order-service")
    assert len(hist) == 2
    assert hist[1].version == "1.1.0"


def test_registry_dependency_topological_sort():
    reg = ServiceRegistry()
    reg.register_service("db", version="1.0.0")
    reg.register_service("auth", version="1.0.0", dependencies=["db"])
    reg.register_service("web", version="1.0.0", dependencies=["auth"])

    order = reg.resolve_dependency_order("web")
    assert order == ["db", "auth", "web"]


def test_registry_circular_dependency_detection():
    reg = ServiceRegistry()
    reg.register_service("svcA", version="1.0.0", dependencies=["svcB"])
    reg.register_service("svcB", version="1.0.0", dependencies=["svcA"])

    with pytest.raises(ValueError, match="Circular dependency detected"):
        reg.resolve_dependency_order("svcA")


def test_registry_bounded_capacity():
    reg = ServiceRegistry(max_services=2)
    reg.register_service("s1")
    reg.register_service("s2")
    reg.register_service("s3")

    assert reg.count() == 2
    assert reg.get_service("s1") is None


def test_registry_list_services():
    reg = ServiceRegistry()
    reg.register_service("s1")
    reg.register_service("s2")
    assert len(reg.list_services()) == 2


# ---------------------------------------------------------------------------
# 4. Container Runtime Abstraction (Tests 17–22)
# ---------------------------------------------------------------------------
def test_runtime_create_container():
    runtime = MockContainerRuntime()
    c = runtime.create_container("worker-1", image="toji/worker:v1")
    assert c.name == "worker-1"
    assert c.state == ContainerState.CREATED
    assert c.is_advisory_only is True


def test_runtime_start_container():
    runtime = MockContainerRuntime()
    c = runtime.create_container("worker-2")
    started = runtime.start_container(c.container_id)
    assert started.state == ContainerState.RUNNING


def test_runtime_stop_container():
    runtime = MockContainerRuntime()
    c = runtime.create_container("worker-3")
    runtime.start_container(c.container_id)
    stopped = runtime.stop_container(c.container_id)
    assert stopped.state == ContainerState.STOPPED


def test_runtime_restart_container():
    runtime = MockContainerRuntime()
    c = runtime.create_container("worker-4")
    restarted = runtime.restart_container(c.container_id)
    assert restarted.state == ContainerState.RUNNING


def test_runtime_list_containers():
    runtime = MockContainerRuntime()
    runtime.create_container("c1")
    runtime.create_container("c2")
    assert len(runtime.list_containers()) == 2


def test_runtime_bounded_eviction():
    runtime = MockContainerRuntime(max_containers=2)
    c1 = runtime.create_container("c1")
    c2 = runtime.create_container("c2")
    c3 = runtime.create_container("c3")

    assert len(runtime.list_containers()) == 2
    assert runtime.get_container(c1.container_id) is None


# ---------------------------------------------------------------------------
# 5. Deployment Planner (Tests 23–27)
# ---------------------------------------------------------------------------
def test_planner_generate_plan():
    planner = DeploymentPlanner()
    reg = ServiceRegistry()
    reg.register_service("db")
    reg.register_service("app", dependencies=["db"])
    cfg = DeploymentConfig()

    plan = planner.generate_plan("app", "1.0.0", cfg, reg)
    assert plan.target_service == "app"
    assert plan.dependency_order == ["db", "app"]
    assert len(plan.rollout_stages) == 3
    assert plan.is_dry_run is True


def test_planner_dependency_ordering():
    planner = DeploymentPlanner()
    reg = ServiceRegistry()
    reg.register_service("app_single")
    cfg = DeploymentConfig()

    plan = planner.generate_plan("app_single", "1.0.0", cfg, reg)
    assert plan.dependency_order == ["app_single"]


def test_planner_rollout_stages_structure():
    planner = DeploymentPlanner()
    reg = ServiceRegistry()
    reg.register_service("svc")
    cfg = DeploymentConfig(deployment_strategy=DeploymentStrategy.CANARY, replica_count=4)

    plan = planner.generate_plan("svc", "1.0.0", cfg, reg)
    assert plan.rollout_stages[1]["traffic_pct"] == 10
    assert plan.rollout_stages[2]["traffic_pct"] == 100


def test_planner_rollback_plan():
    planner = DeploymentPlanner()
    reg = ServiceRegistry()
    reg.register_service("svc")
    cfg = DeploymentConfig()

    plan = planner.generate_plan("svc", "1.0.0", cfg, reg)
    assert "actions" in plan.rollback_plan
    assert len(plan.rollback_plan["actions"]) > 0


def test_planner_advisory_flag():
    planner = DeploymentPlanner()
    reg = ServiceRegistry()
    reg.register_service("svc")
    cfg = DeploymentConfig()

    plan = planner.generate_plan("svc", "1.0.0", cfg, reg)
    assert plan.is_advisory_only is True


# ---------------------------------------------------------------------------
# 6. Deployment Validator (Tests 28–32)
# ---------------------------------------------------------------------------
def test_validator_valid_config():
    val = DeploymentValidator()
    reg = ServiceRegistry()
    reg.register_service("valid-svc")
    cfg = DeploymentConfig(cpu_allocation=1.0, memory_allocation_mb=512)

    rep = val.validate("valid-svc", cfg, reg)
    assert rep.is_valid is True
    assert len(rep.errors) == 0


def test_validator_cpu_limit_exceeded():
    val = DeploymentValidator()
    reg = ServiceRegistry()
    reg.register_service("high-cpu-svc")
    cfg = DeploymentConfig(cpu_allocation=8.0, max_cpu_limit=4.0)

    rep = val.validate("high-cpu-svc", cfg, reg)
    assert rep.is_valid is False
    assert any("CPU allocation" in e for e in rep.errors)


def test_validator_memory_limit_exceeded():
    val = DeploymentValidator()
    reg = ServiceRegistry()
    reg.register_service("high-mem-svc")
    cfg = DeploymentConfig(memory_allocation_mb=8192, max_memory_limit_mb=4096)

    rep = val.validate("high-mem-svc", cfg, reg)
    assert rep.is_valid is False
    assert any("Memory allocation" in e for e in rep.errors)


def test_validator_unregistered_dependency_error():
    val = DeploymentValidator()
    reg = ServiceRegistry()
    reg.register_service("svc_with_missing_dep", dependencies=["missing_service"])
    cfg = DeploymentConfig()

    rep = val.validate("svc_with_missing_dep", cfg, reg)
    assert rep.is_valid is False
    assert any("missing_service" in e for e in rep.errors)


def test_validator_canary_replica_warning():
    val = DeploymentValidator()
    reg = ServiceRegistry()
    reg.register_service("canary_svc")
    cfg = DeploymentConfig(deployment_strategy=DeploymentStrategy.CANARY, replica_count=1)

    rep = val.validate("canary_svc", cfg, reg)
    assert rep.is_valid is True
    assert any("replica_count >= 2" in w for w in rep.warnings)


# ---------------------------------------------------------------------------
# 7. Health Monitor (Tests 33–38)
# ---------------------------------------------------------------------------
def test_health_monitor_record_heartbeat():
    hm = HealthMonitor()
    rec = hm.record_heartbeat("payment-service", is_alive=True, is_ready=True)
    assert rec.service_name == "payment-service"
    assert rec.is_alive is True
    assert rec.is_ready is True
    assert rec.is_advisory_only is True


def test_health_monitor_get_latest():
    hm = HealthMonitor()
    hm.record_heartbeat("s1", is_alive=True, is_ready=False)
    hm.record_heartbeat("s1", is_alive=True, is_ready=True)

    latest = hm.get_health("s1")
    assert latest is not None
    assert latest.is_ready is True


def test_health_monitor_history():
    hm = HealthMonitor()
    hm.record_heartbeat("s2", is_alive=True)
    hm.record_heartbeat("s2", is_alive=False)

    hist = hm.get_health_history("s2")
    assert len(hist) == 2


def test_health_monitor_is_healthy():
    hm = HealthMonitor()
    hm.record_heartbeat("good_svc", is_alive=True, is_ready=True)
    hm.record_heartbeat("bad_svc", is_alive=True, is_ready=False)

    assert hm.is_service_healthy("good_svc") is True
    assert hm.is_service_healthy("bad_svc") is False
    assert hm.is_service_healthy("nonexistent") is False


def test_health_monitor_generate_report():
    hm = HealthMonitor()
    hm.record_heartbeat("s1", is_alive=True, is_ready=True)
    hm.record_heartbeat("s2", is_alive=False, is_ready=False)

    rep = hm.generate_health_report()
    assert rep["total_services"] == 2
    assert rep["healthy_services"] == 1
    assert rep["degraded_services"] == 1
    assert rep["overall_status"] == "DEGRADED"


def test_health_monitor_bounded_history():
    hm = HealthMonitor(max_history_per_service=2)
    hm.record_heartbeat("s_bnd", status_message="h1")
    hm.record_heartbeat("s_bnd", status_message="h2")
    hm.record_heartbeat("s_bnd", status_message="h3")

    hist = hm.get_health_history("s_bnd")
    assert len(hist) == 2
    assert hist[0].status_message == "h2"
    assert hist[1].status_message == "h3"


# ---------------------------------------------------------------------------
# 8. Deployment Manager Lifecycle (Tests 39–45)
# ---------------------------------------------------------------------------
def test_manager_create_deployment(dep_mgr):
    desc = dep_mgr.create_deployment("order-api", version="1.0.0")
    assert desc.service_name == "order-api"
    assert desc.status == DeploymentStatus.CREATED
    assert "plan_id" in desc.plan_summary


def test_manager_validate_deployment(dep_mgr):
    desc = dep_mgr.create_deployment("inventory-service")
    report = dep_mgr.validate_deployment(desc.deployment_id)
    assert report.is_valid is True

    updated = dep_mgr.get_deployment(desc.deployment_id)
    assert updated.status == DeploymentStatus.VALIDATED


def test_manager_validate_invalid_deployment(dep_mgr):
    cfg = DeploymentConfig(cpu_allocation=16.0, max_cpu_limit=4.0)
    desc = dep_mgr.create_deployment("over_cpu_service", config=cfg)
    report = dep_mgr.validate_deployment(desc.deployment_id)
    assert report.is_valid is False

    updated = dep_mgr.get_deployment(desc.deployment_id)
    assert updated.status == DeploymentStatus.CREATED  # Not updated to VALIDATED


def test_manager_approve_deployment(dep_mgr):
    desc = dep_mgr.create_deployment("shipping-service")
    dep_mgr.validate_deployment(desc.deployment_id)
    approved = dep_mgr.approve_deployment(desc.deployment_id, approver="admin_user")

    assert approved.status == DeploymentStatus.APPROVED
    assert len(dep_mgr.runtime.list_containers()) == 1


def test_manager_cancel_deployment(dep_mgr):
    desc = dep_mgr.create_deployment("cancel-me")
    cancelled = dep_mgr.cancel_deployment(desc.deployment_id, reason="Budget freeze")
    assert cancelled.status == DeploymentStatus.CANCELLED
    assert "Budget freeze" in cancelled.error_message


def test_manager_archive_deployment(dep_mgr):
    desc = dep_mgr.create_deployment("archive-me")
    archived = dep_mgr.archive_deployment(desc.deployment_id)
    assert archived.status == DeploymentStatus.ARCHIVED


def test_manager_list_deployments_filtered(dep_mgr):
    d1 = dep_mgr.create_deployment("s1")
    d2 = dep_mgr.create_deployment("s2")
    dep_mgr.validate_deployment(d1.deployment_id)

    validated = dep_mgr.list_deployments(status=DeploymentStatus.VALIDATED)
    created = dep_mgr.list_deployments(status=DeploymentStatus.CREATED)

    assert len(validated) == 1
    assert len(created) == 1


# ---------------------------------------------------------------------------
# 9. Events (Tests 46–53)
# ---------------------------------------------------------------------------
def test_event_deployment_created(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("DeploymentCreated", lambda e: evts.append(e))
    dep_mgr.create_deployment("evt-svc")
    assert len(evts) == 1
    assert evts[0].event_type == "DeploymentCreated"


def test_event_deployment_validated(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("DeploymentValidated", lambda e: evts.append(e))
    d = dep_mgr.create_deployment("evt-val")
    dep_mgr.validate_deployment(d.deployment_id)
    assert len(evts) == 1
    assert evts[0].event_type == "DeploymentValidated"


def test_event_deployment_approved(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("DeploymentApproved", lambda e: evts.append(e))
    d = dep_mgr.create_deployment("evt-appr")
    dep_mgr.approve_deployment(d.deployment_id)
    assert len(evts) == 1
    assert evts[0].event_type == "DeploymentApproved"


def test_event_deployment_cancelled(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("DeploymentCancelled", lambda e: evts.append(e))
    d = dep_mgr.create_deployment("evt-can")
    dep_mgr.cancel_deployment(d.deployment_id)
    assert len(evts) == 1
    assert evts[0].event_type == "DeploymentCancelled"


def test_event_deployment_archived(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("DeploymentArchived", lambda e: evts.append(e))
    d = dep_mgr.create_deployment("evt-arch")
    dep_mgr.archive_deployment(d.deployment_id)
    assert len(evts) == 1
    assert evts[0].event_type == "DeploymentArchived"


def test_event_service_registered(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("ServiceRegistered", lambda e: evts.append(e))
    dep_mgr.register_service("evt-reg-svc", "1.0.0")
    assert len(evts) == 1
    assert evts[0].service_name == "evt-reg-svc"


def test_event_health_status_updated(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("HealthStatusUpdated", lambda e: evts.append(e))
    dep_mgr.record_health_heartbeat("evt-health", is_alive=True)
    assert len(evts) == 1
    assert evts[0].service_name == "evt-health"


def test_event_runtime_operation_performed(event_bus, dep_mgr):
    evts = []
    event_bus.subscribe("RuntimeOperationPerformed", lambda e: evts.append(e))
    d = dep_mgr.create_deployment("evt-runtime")
    dep_mgr.approve_deployment(d.deployment_id)
    assert len(evts) == 1
    assert evts[0].operation == "start_container"


# ---------------------------------------------------------------------------
# 10. Thread Safety & Performance (Tests 54–56)
# ---------------------------------------------------------------------------
def test_thread_safety_concurrent_operations(dep_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(5):
                s_name = f"conc_svc_{i}_{j}"
                dep_mgr.register_service(s_name)
                d = dep_mgr.create_deployment(s_name)
                dep_mgr.validate_deployment(d.deployment_id)
                dep_mgr.record_health_heartbeat(s_name)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert dep_mgr.registry.count() >= 25
    assert dep_mgr.count() == 25


def test_performance_5000_deployments():
    mgr = DeploymentManager(max_deployments=6000)
    start_t = time.perf_counter()

    for i in range(5000):
        mgr.create_deployment(f"scale_svc_{i}")

    elapsed = time.perf_counter() - start_t
    assert mgr.count() == 5000
    assert elapsed < 5.0  # Must be fast under capacity


def test_performance_2000_services():
    reg = ServiceRegistry(max_services=2500)
    start_t = time.perf_counter()

    for i in range(2000):
        reg.register_service(f"scale_reg_svc_{i}")

    elapsed = time.perf_counter() - start_t
    assert reg.count() == 2000
    assert elapsed < 5.0  # Must be fast under capacity


# ---------------------------------------------------------------------------
# 11. Dependency Injection & Mockability (Tests 57–58)
# ---------------------------------------------------------------------------
def test_dependency_injection_custom_runtime():
    runtime = MockContainerRuntime()
    mgr = DeploymentManager(runtime=runtime)
    assert mgr.runtime is runtime


def test_dependency_injection_custom_registry():
    registry = ServiceRegistry()
    mgr = DeploymentManager(registry=registry)
    assert mgr.registry is registry


# ---------------------------------------------------------------------------
# 12. Architecture Boundary Enforcement & Regression (Tests 59–60)
# ---------------------------------------------------------------------------
def test_regression_sprint12a_unaffected():
    from infrastructure.infrastructure_manager import InfrastructureManager
    infra = InfrastructureManager()
    sess = infra.initialize()
    assert sess is not None


def test_architecture_boundary_enforcement():
    dep_dir = pathlib.Path(__file__).parent.parent / "deployment"
    forbidden = {"broker", "strategy", "execution", "live_trading", "paper_trading", "boto3", "docker"}

    violations = []
    for py_file in dep_dir.rglob("*.py"):
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
