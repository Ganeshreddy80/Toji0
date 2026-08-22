"""Comprehensive Test Suite — Sprint 11B Training Pipeline (45 tests)."""

import ast
import pathlib
import threading
import time
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from self_learning.artifact_manager import ArtifactManager, ArtifactRecord
from self_learning.checkpoint_manager import CheckpointManager, CheckpointRecord
from self_learning.metrics_collector import MetricsCollector, PipelineMetrics
from self_learning.pipeline_state import PipelineConfig, PipelineRecord, PipelineStatus
from self_learning.resource_allocator import ResourceAllocator, ResourceReservation
from self_learning.training_events import (
    ArtifactRegistered,
    CheckpointSaved,
    PipelineCancelled,
    PipelineCompleted,
    PipelineCreated,
    PipelineFailed,
    PipelineQueued,
    PipelineStarted,
)
from self_learning.training_executor import ExecutionResult, TrainingExecutor
from self_learning.training_pipeline import TrainingPipelineManager
from self_learning.training_scheduler import TrainingScheduler
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def pipeline_mgr(event_bus):
    return TrainingPipelineManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. Pipeline Lifecycle
# ---------------------------------------------------------------------------
def test_pipeline_created(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p1", "model_1", "dataset_1")
    assert p.status == PipelineStatus.CREATED
    assert p.config.name == "p1"
    assert p.is_advisory_only is True


def test_pipeline_queued(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p2", "model_1", "dataset_1", priority=5)
    q = pipeline_mgr.queue_pipeline(p.pipeline_id)
    assert q.status == PipelineStatus.QUEUED


def test_pipeline_execution_success(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p3", "model_1", "dataset_1")
    executed = pipeline_mgr.execute_pipeline(p.pipeline_id)
    assert executed.status == PipelineStatus.COMPLETED
    assert executed.completed_at is not None


def test_pipeline_execution_failure(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p4", "model_1", "dataset_1")

    def failing_trainer(config):
        raise ValueError("Simulated training crash")

    executed = pipeline_mgr.execute_pipeline(p.pipeline_id, custom_trainer=failing_trainer)
    assert executed.status == PipelineStatus.FAILED
    assert "Simulated training crash" in executed.error_message


def test_pipeline_cancellation_created(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p5", "model_1", "dataset_1")
    cancelled = pipeline_mgr.cancel_pipeline(p.pipeline_id, reason="User stop")
    assert cancelled.status == PipelineStatus.CANCELLED
    assert "User stop" in cancelled.error_message


def test_pipeline_cancellation_queued(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p6", "model_1", "dataset_1")
    pipeline_mgr.queue_pipeline(p.pipeline_id)
    cancelled = pipeline_mgr.cancel_pipeline(p.pipeline_id)
    assert cancelled.status == PipelineStatus.CANCELLED


def test_pipeline_retry(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p7", "model_1", "dataset_1", max_retries=2)

    # Fail first attempt
    def fail_once(config):
        raise ValueError("Transient error")

    failed = pipeline_mgr.execute_pipeline(p.pipeline_id, custom_trainer=fail_once)
    assert failed.status == PipelineStatus.FAILED

    # Retry should succeed with default trainer
    retried = pipeline_mgr.retry_pipeline(p.pipeline_id)
    assert retried.status == PipelineStatus.COMPLETED
    assert retried.current_retry >= 1


def test_pipeline_retry_max_reached(pipeline_mgr):
    p = pipeline_mgr.create_pipeline("p8", "model_1", "dataset_1", max_retries=0)
    failed = pipeline_mgr.execute_pipeline(p.pipeline_id, custom_trainer=lambda c: 1 / 0)
    assert failed.status == PipelineStatus.FAILED

    # Retry blocked because max_retries == 0
    blocked = pipeline_mgr.retry_pipeline(p.pipeline_id)
    assert blocked.status == PipelineStatus.FAILED


def test_pipeline_list_status(pipeline_mgr):
    p1 = pipeline_mgr.create_pipeline("pl1", "m1", "d1")
    p2 = pipeline_mgr.create_pipeline("pl2", "m2", "d2")
    pipeline_mgr.execute_pipeline(p1.pipeline_id)

    completed = pipeline_mgr.list_pipelines(status=PipelineStatus.COMPLETED)
    created = pipeline_mgr.list_pipelines(status=PipelineStatus.CREATED)

    assert len(completed) == 1
    assert len(created) == 1


# ---------------------------------------------------------------------------
# 2. Scheduler
# ---------------------------------------------------------------------------
def test_scheduler_priority_order():
    scheduler = TrainingScheduler()
    cfg1 = PipelineConfig(name="low", model_id="m", dataset_id="d", priority=1)
    cfg2 = PipelineConfig(name="high", model_id="m", dataset_id="d", priority=10)

    scheduler.queue_job(cfg1)
    scheduler.queue_job(cfg2)

    popped1 = scheduler.pop_next_job()
    popped2 = scheduler.pop_next_job()

    assert popped1.name == "high"
    assert popped2.name == "low"


def test_scheduler_fifo_order_same_priority():
    scheduler = TrainingScheduler()
    cfg1 = PipelineConfig(name="first", model_id="m", dataset_id="d", priority=5)
    cfg2 = PipelineConfig(name="second", model_id="m", dataset_id="d", priority=5)

    scheduler.queue_job(cfg1)
    scheduler.queue_job(cfg2)

    assert scheduler.pop_next_job().name == "first"
    assert scheduler.pop_next_job().name == "second"


def test_scheduler_cancel_queued():
    scheduler = TrainingScheduler()
    cfg = PipelineConfig(name="cancel_me", model_id="m", dataset_id="d")
    scheduler.queue_job(cfg)
    ok = scheduler.cancel_queued_job(cfg.pipeline_id)
    assert ok is True
    assert scheduler.pop_next_job() is None


def test_scheduler_queue_full():
    scheduler = TrainingScheduler(max_queue_size=2)
    cfg1 = PipelineConfig(name="c1", model_id="m", dataset_id="d")
    cfg2 = PipelineConfig(name="c2", model_id="m", dataset_id="d")
    cfg3 = PipelineConfig(name="c3", model_id="m", dataset_id="d")

    assert scheduler.queue_job(cfg1) is True
    assert scheduler.queue_job(cfg2) is True
    assert scheduler.queue_job(cfg3) is False


# ---------------------------------------------------------------------------
# 3. Executor & Resource Allocator
# ---------------------------------------------------------------------------
def test_executor_resource_allocation_failure():
    allocator = ResourceAllocator(total_cpu_cores=1.0, total_memory_mb=1000.0)
    executor = TrainingExecutor(resource_allocator=allocator)
    cfg = PipelineConfig(name="greedy", model_id="m", dataset_id="d", cpu_cores=4.0)

    res = executor.execute_stage(cfg)
    assert res.success is False
    assert "Resource reservation failed" in res.error_message


def test_executor_timeout():
    executor = TrainingExecutor()
    cfg = PipelineConfig(name="slow", model_id="m", dataset_id="d", timeout_seconds=0.01)

    def slow_trainer(config):
        time.sleep(0.05)
        return {"loss": 0.1}

    res = executor.execute_stage(cfg, custom_trainer=slow_trainer)
    assert res.success is False
    assert "timed out" in res.error_message


def test_executor_retry_loop():
    executor = TrainingExecutor()
    cfg = PipelineConfig(name="flaky", model_id="m", dataset_id="d", max_retries=2)

    attempts = 0

    def flaky_trainer(config):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("Temporary failure")
        return {"loss": 0.05}

    res = executor.execute_stage(cfg, custom_trainer=flaky_trainer)
    assert res.success is True
    assert res.retries_used == 1


def test_resource_allocator_reserve():
    allocator = ResourceAllocator(total_cpu_cores=8.0, total_memory_mb=16000.0)
    res = allocator.reserve_resources("p1", cpu_cores=4.0, memory_mb=8000.0)
    assert res is not None
    assert res.cpu_cores == 4.0

    avail = allocator.available_resources()
    assert avail["available_cpu"] == 4.0
    assert avail["available_memory_mb"] == 8000.0


def test_resource_allocator_insufficient():
    allocator = ResourceAllocator(total_cpu_cores=2.0, total_memory_mb=4000.0)
    res = allocator.reserve_resources("p1", cpu_cores=4.0, memory_mb=8000.0)
    assert res is None


def test_resource_allocator_release():
    allocator = ResourceAllocator(total_cpu_cores=4.0, total_memory_mb=8000.0)
    res = allocator.reserve_resources("p1", cpu_cores=4.0, memory_mb=8000.0)
    assert allocator.available_resources()["available_cpu"] == 0.0

    ok = allocator.release_resources(res.reservation_id)
    assert ok is True
    assert allocator.available_resources()["available_cpu"] == 4.0


def test_resource_allocator_release_by_pipeline_id():
    allocator = ResourceAllocator(total_cpu_cores=4.0, total_memory_mb=8000.0)
    allocator.reserve_resources("p1", cpu_cores=2.0, memory_mb=4000.0)
    ok = allocator.release_resources("p1")
    assert ok is True
    assert allocator.available_resources()["available_cpu"] == 4.0


# ---------------------------------------------------------------------------
# 4. Checkpoint Manager
# ---------------------------------------------------------------------------
def test_checkpoint_manager_save(event_bus):
    mgr = CheckpointManager(event_bus=event_bus)
    ckpt = mgr.save_checkpoint("pipe_1", epoch=5, step=500, state_dict={"w": [1, 2, 3]})
    assert ckpt.pipeline_id == "pipe_1"
    assert ckpt.epoch == 5
    assert ckpt.state_dict["w"] == [1, 2, 3]


def test_checkpoint_manager_load():
    mgr = CheckpointManager()
    saved = mgr.save_checkpoint("pipe_2", epoch=1)
    loaded = mgr.load_checkpoint(saved.checkpoint_id)
    assert loaded is not None
    assert loaded.epoch == 1


def test_checkpoint_manager_list():
    mgr = CheckpointManager()
    mgr.save_checkpoint("pipe_a", epoch=1)
    mgr.save_checkpoint("pipe_a", epoch=2)
    mgr.save_checkpoint("pipe_b", epoch=1)

    pipe_a_ckpts = mgr.list_checkpoints("pipe_a")
    assert len(pipe_a_ckpts) == 2


def test_checkpoint_manager_delete():
    mgr = CheckpointManager()
    ckpt = mgr.save_checkpoint("pipe_c", epoch=1)
    deleted = mgr.delete_checkpoint(ckpt.checkpoint_id)
    assert deleted is True
    assert mgr.load_checkpoint(ckpt.checkpoint_id) is None


def test_checkpoint_manager_bounded_eviction():
    mgr = CheckpointManager(max_checkpoints=2)
    c1 = mgr.save_checkpoint("p", epoch=1)
    c2 = mgr.save_checkpoint("p", epoch=2)
    c3 = mgr.save_checkpoint("p", epoch=3)

    assert mgr.count() == 2
    assert mgr.load_checkpoint(c1.checkpoint_id) is None  # Evicted
    assert mgr.load_checkpoint(c3.checkpoint_id) is not None


# ---------------------------------------------------------------------------
# 5. Artifact Manager
# ---------------------------------------------------------------------------
def test_artifact_manager_register(event_bus):
    mgr = ArtifactManager(event_bus=event_bus)
    art = mgr.register_artifact("weights", "pipe_1", artifact_type="model", version="1.0.0")
    assert art.name == "weights"
    assert art.version == "1.0.0"


def test_artifact_manager_retrieve():
    mgr = ArtifactManager()
    art = mgr.register_artifact("weights", "pipe_1", version="2.0.0", uri_or_payload="/models/v2.pt")
    retrieved = mgr.get_by_name_and_version("weights", "2.0.0")
    assert retrieved is not None
    assert retrieved.uri_or_payload == "/models/v2.pt"


def test_artifact_manager_list():
    mgr = ArtifactManager()
    mgr.register_artifact("art1", "pipe_x")
    mgr.register_artifact("art2", "pipe_x")
    mgr.register_artifact("art3", "pipe_y")

    x_artifacts = mgr.list_artifacts("pipe_x")
    assert len(x_artifacts) == 2


def test_artifact_manager_delete():
    mgr = ArtifactManager()
    art = mgr.register_artifact("art_temp", "pipe_z")
    ok = mgr.delete_artifact(art.artifact_id)
    assert ok is True
    assert mgr.retrieve_artifact(art.artifact_id) is None


def test_artifact_manager_bounded_eviction():
    mgr = ArtifactManager(max_artifacts=2)
    a1 = mgr.register_artifact("a1", "p")
    a2 = mgr.register_artifact("a2", "p")
    a3 = mgr.register_artifact("a3", "p")

    assert mgr.count() == 2
    assert mgr.retrieve_artifact(a1.artifact_id) is None


# ---------------------------------------------------------------------------
# 6. Metrics Collector
# ---------------------------------------------------------------------------
def test_metrics_collector_record():
    collector = MetricsCollector()
    m = collector.record_metrics(
        "pipe_m",
        duration_seconds=12.5,
        accuracy=0.96,
        loss=0.08,
        throughput=300.0,
    )
    assert m.duration_seconds == 12.5
    assert m.accuracy == 0.96
    assert m.loss == 0.08
    assert m.throughput == 300.0


def test_metrics_collector_latest():
    collector = MetricsCollector()
    collector.record_metrics("pipe_m", accuracy=0.8)
    collector.record_metrics("pipe_m", accuracy=0.9)

    latest = collector.get_latest_metrics("pipe_m")
    assert latest.accuracy == 0.9


def test_metrics_collector_history():
    collector = MetricsCollector()
    collector.record_metrics("pipe_h", loss=0.5)
    collector.record_metrics("pipe_h", loss=0.3)
    history = collector.get_metrics("pipe_h")
    assert len(history) == 2


def test_metrics_collector_bounded_history():
    collector = MetricsCollector(max_history_per_pipeline=2)
    collector.record_metrics("pipe_b", loss=0.3)
    collector.record_metrics("pipe_b", loss=0.2)
    collector.record_metrics("pipe_b", loss=0.1)

    history = collector.get_metrics("pipe_b")
    assert len(history) == 2
    assert history[0].loss == 0.2
    assert history[1].loss == 0.1


# ---------------------------------------------------------------------------
# 7. Events
# ---------------------------------------------------------------------------
def test_event_pipeline_created(event_bus, pipeline_mgr):
    events = []
    event_bus.subscribe("PipelineCreated", lambda e: events.append(e))
    pipeline_mgr.create_pipeline("evt_pipe", "m", "d")
    assert len(events) == 1
    assert events[0].event_type == "PipelineCreated"


def test_event_pipeline_queued(event_bus, pipeline_mgr):
    events = []
    event_bus.subscribe("PipelineQueued", lambda e: events.append(e))
    p = pipeline_mgr.create_pipeline("evt_q", "m", "d")
    pipeline_mgr.queue_pipeline(p.pipeline_id)
    assert len(events) == 1
    assert events[0].event_type == "PipelineQueued"


def test_event_pipeline_started_completed(event_bus, pipeline_mgr):
    started_evts = []
    completed_evts = []
    event_bus.subscribe("PipelineStarted", lambda e: started_evts.append(e))
    event_bus.subscribe("PipelineCompleted", lambda e: completed_evts.append(e))

    p = pipeline_mgr.create_pipeline("evt_exec", "m", "d")
    pipeline_mgr.execute_pipeline(p.pipeline_id)

    assert len(started_evts) == 1
    assert len(completed_evts) == 1


def test_event_pipeline_failed(event_bus, pipeline_mgr):
    events = []
    event_bus.subscribe("PipelineFailed", lambda e: events.append(e))
    p = pipeline_mgr.create_pipeline("evt_fail", "m", "d")
    pipeline_mgr.execute_pipeline(p.pipeline_id, custom_trainer=lambda c: 1 / 0)
    assert len(events) == 1
    assert events[0].event_type == "PipelineFailed"


def test_event_pipeline_cancelled(event_bus, pipeline_mgr):
    events = []
    event_bus.subscribe("PipelineCancelled", lambda e: events.append(e))
    p = pipeline_mgr.create_pipeline("evt_cancel", "m", "d")
    pipeline_mgr.cancel_pipeline(p.pipeline_id)
    assert len(events) == 1
    assert events[0].event_type == "PipelineCancelled"


def test_event_checkpoint_saved(event_bus):
    events = []
    event_bus.subscribe("CheckpointSaved", lambda e: events.append(e))
    mgr = CheckpointManager(event_bus=event_bus)
    mgr.save_checkpoint("pipe_1", epoch=10)
    assert len(events) == 1
    assert events[0].epoch == 10


def test_event_artifact_registered(event_bus):
    events = []
    event_bus.subscribe("ArtifactRegistered", lambda e: events.append(e))
    mgr = ArtifactManager(event_bus=event_bus)
    mgr.register_artifact("weights", "pipe_1")
    assert len(events) == 1
    assert events[0].artifact_name == "weights"


# ---------------------------------------------------------------------------
# 8. Thread Safety & Performance
# ---------------------------------------------------------------------------
def test_thread_safety_concurrent_pipelines(pipeline_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(5):
                p = pipeline_mgr.create_pipeline(f"concurrent_{i}_{j}", "m", "d")
                pipeline_mgr.execute_pipeline(p.pipeline_id)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert pipeline_mgr.count() == 25


def test_performance_100_concurrent_pipelines():
    pipeline_mgr = TrainingPipelineManager(max_pipelines=200)
    start_t = time.perf_counter()

    for i in range(100):
        pipeline_mgr.create_pipeline(f"scale_pipe_{i}", "m", "d")

    elapsed = time.perf_counter() - start_t
    assert pipeline_mgr.count() == 100
    assert elapsed < 5.0  # Must be fast under capacity


# ---------------------------------------------------------------------------
# 9. Regression & Architecture Boundary
# ---------------------------------------------------------------------------
def test_regression_paper_trading_unaffected():
    from paper_trading import PaperOrchestrator
    orch = PaperOrchestrator(initial_capital=50000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()


def test_architecture_boundary_enforcement():
    sl_dir = pathlib.Path(__file__).parent.parent / "self_learning"
    forbidden = {"broker", "strategy", "execution", "paper_trading", "mission_control", "aws", "live_trading"}

    violations = []
    for py_file in sl_dir.rglob("*.py"):
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


# 46. Hardening C-01 — Concurrent cancellation is respected
def test_concurrent_cancellation_respected(event_bus):
    mgr = TrainingPipelineManager(event_bus=event_bus)
    p = mgr.create_pipeline("concurrent_cancel", "m", "d")

    execution_started = threading.Event()
    cancel_done = threading.Event()

    def slow_trainer(config):
        execution_started.set()
        cancel_done.wait(timeout=2.0)
        return {"loss": 0.1}

    def run_executor():
        mgr.execute_pipeline(p.pipeline_id, custom_trainer=slow_trainer)

    t = threading.Thread(target=run_executor)
    t.start()

    assert execution_started.wait(timeout=2.0)
    cancelled_rec = mgr.cancel_pipeline(p.pipeline_id)
    assert cancelled_rec.status == PipelineStatus.CANCELLED
    cancel_done.set()

    t.join(timeout=2.0)

    final_rec = mgr.get_pipeline(p.pipeline_id)
    assert final_rec.status == PipelineStatus.CANCELLED


# 47. Hardening M-02 — Completed pipeline cannot be cancelled
def test_completed_pipeline_cannot_be_cancelled(event_bus):
    cancelled_events = []
    event_bus.subscribe("PipelineCancelled", lambda e: cancelled_events.append(e))

    mgr = TrainingPipelineManager(event_bus=event_bus)
    p = mgr.create_pipeline("completed_p", "m", "d")
    executed = mgr.execute_pipeline(p.pipeline_id)
    assert executed.status == PipelineStatus.COMPLETED

    res = mgr.cancel_pipeline(p.pipeline_id)
    assert res.status == PipelineStatus.COMPLETED
    assert len(cancelled_events) == 0

