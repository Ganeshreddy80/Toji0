"""Comprehensive unit and integration tests for TOJI Experiment Manager & Strategy Scheduler (R38-R39).
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

# Subsystems
from research_platform.experiment_manager.orchestrator import ExperimentManagerOrchestrator
from research_platform.experiment_manager.models import ReproducibilitySnapshot, Experiment
from research_platform.experiment_manager.plugin import ExperimentManagerPlugin

from research_platform.scheduler.orchestrator import StrategySchedulerOrchestrator
from research_platform.scheduler.models import ExecutionJob
from research_platform.scheduler.plugin import StrategySchedulerPlugin

# Integration targets
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    ops_orch = OperationsOrchestrator(event_bus, container=c)
    c.register("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator", instance=ops_orch)

    return c


@pytest.fixture
def exp_orch(event_bus, container):
    return ExperimentManagerOrchestrator(event_bus, container=container)


@pytest.fixture
def sched_orch(event_bus, container):
    return StrategySchedulerOrchestrator(event_bus, container=container)


# ─────────────────────────────────────────────────────────────────────
# 1-30: EXPERIMENT MANAGER TESTS (R38)
# ─────────────────────────────────────────────────────────────────────

def test_exp_creation_success(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="dataset-123", git_hash="git-123", config_id="cfg-1")
    res = exp_orch.create_experiment("e1", "Backtest Run 1", "Desc", ["tag-1"], "group-1", repro)
    assert res.experiment_id == "e1"
    assert res.name == "Backtest Run 1"
    assert res.status == "DRAFT"


def test_exp_blank_id_failure(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    with pytest.raises(ValueError, match="Experiment ID and Name"):
        exp_orch.create_experiment("", "Run", "Desc", [], "g", repro)


def test_exp_blank_name_failure(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    with pytest.raises(ValueError, match="Experiment ID and Name"):
        exp_orch.create_experiment("e1", "", "Desc", [], "g", repro)


def test_exp_archive_success(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    res = exp_orch.archive_experiment("e1")
    assert res.status == "ARCHIVED"


def test_exp_archive_missing_failure(exp_orch):
    with pytest.raises(ValueError, match="not found"):
        exp_orch.archive_experiment("missing")


def test_exp_clone_success(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    cloned = exp_orch.clone_experiment("e1", "e1-clone")
    assert cloned.experiment_id == "e1-clone"
    assert "Clone of" in cloned.name


def test_exp_clone_missing_failure(exp_orch):
    with pytest.raises(ValueError, match="not found"):
        exp_orch.clone_experiment("missing", "clone")


def test_exp_results_saving_success(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    res = exp_orch.update_experiment_results("e1", {"sharpe_ratio": 1.8, "pnl": 5000.0})
    assert res.status == "COMPLETED"
    assert res.results["sharpe_ratio"] == 1.8


def test_exp_compare_runs_identical_seed(exp_orch):
    repro1 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    repro2 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro1)
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "g", repro2)
    
    comp = exp_orch.evaluate_comparison(["e1", "e2"])
    assert "random_seed" not in comp.differing_keys


def test_exp_compare_runs_differing_seed(exp_orch):
    repro1 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    repro2 = ReproducibilitySnapshot(random_seed=99, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro1)
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "g", repro2)
    
    comp = exp_orch.evaluate_comparison(["e1", "e2"])
    assert "random_seed" in comp.differing_keys


def test_exp_leaderboard_sorting(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro)
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "g", repro)
    
    exp_orch.update_experiment_results("e1", {"sharpe_ratio": 1.2, "pnl": 2000.0})
    exp_orch.update_experiment_results("e2", {"sharpe_ratio": 2.1, "pnl": 5000.0})
    
    leaderboard = exp_orch.update_leaderboard("Leaderboard-1", "g")
    assert len(leaderboard.entries) == 2
    assert leaderboard.entries[0].strategy_id == "e2"
    assert leaderboard.entries[0].rank == 1
    assert leaderboard.entries[1].strategy_id == "e1"
    assert leaderboard.entries[1].rank == 2


def test_exp_reproducibility_engine_match(exp_orch):
    repro1 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    repro2 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    assert exp_orch.reproducibility_engine.verify_reproducibility(repro1, repro2) is True


def test_exp_reproducibility_engine_differing(exp_orch):
    repro1 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    repro2 = ReproducibilitySnapshot(random_seed=99, dataset_hash="d", git_hash="g", config_id="c")
    assert exp_orch.reproducibility_engine.verify_reproducibility(repro1, repro2) is False


def test_exp_verify_reproducibility_action(exp_orch):
    repro1 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    repro2 = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro1)
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "g", repro2)
    assert exp_orch.verify_reproducibility("e1", "e2") is True


def test_exp_verify_reproducibility_action_missing(exp_orch):
    assert exp_orch.verify_reproducibility("missing-1", "missing-2") is False


def test_exp_repository_list(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro)
    assert len(exp_orch.repository.list_experiments()) == 1


def test_exp_thread_safety_saves(exp_orch):
    def worker(idx):
        repro = ReproducibilitySnapshot(random_seed=idx, dataset_hash="d", git_hash="g", config_id="c")
        exp_orch.create_experiment(f"thread-e-{idx}", "Run", "Desc", [], "g", repro)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(exp_orch.repository.list_experiments()) == 10


def test_exp_plugin_registration(container):
    plugin = ExperimentManagerPlugin(container)
    plugin.initialize()
    orch = container.resolve(ExperimentManagerOrchestrator)
    assert orch is not None


def test_exp_created_event(exp_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.experiment_created", sub)

    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    assert len(events) == 1


def test_exp_compared_event(exp_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.experiment_compared", sub)

    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    exp_orch.evaluate_comparison(["e1"])
    assert len(events) == 1


def test_exp_leaderboard_ranked_event(exp_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.experiment_leaderboard_ranked", sub)

    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    exp_orch.update_experiment_results("e1", {"sharpe_ratio": 2.1, "pnl": 5000.0})
    exp_orch.update_leaderboard("Leaderboard-1", "g")
    assert len(events) == 1


def test_exp_memory_integration(exp_orch, container):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("research")) == 1


def test_exp_kg_integration(exp_orch, container):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "e1"), None) is not None


# ─────────────────────────────────────────────────────────────────────
# 31-61: STRATEGY SCHEDULER TESTS (R39)
# ─────────────────────────────────────────────────────────────────────

def test_sched_schedule_success(sched_orch):
    res = sched_orch.schedule_job("j1", "Backtest Pipeline", "BACKTEST", "0 0 * * *", 10)
    assert res.job_id == "j1"
    assert res.task_type == "BACKTEST"
    assert res.schedule_expr == "0 0 * * *"
    assert res.priority == 10
    assert res.status == "PENDING"


def test_sched_blank_id_failure(sched_orch):
    with pytest.raises(ValueError, match="Job ID and Name"):
        sched_orch.schedule_job("", "Name", "BACKTEST", "expr", 10)


def test_sched_blank_name_failure(sched_orch):
    with pytest.raises(ValueError, match="Job ID and Name"):
        sched_orch.schedule_job("j1", "", "BACKTEST", "expr", 10)


def test_sched_invalid_task_type_failure(sched_orch):
    with pytest.raises(ValueError, match="Invalid Task Type"):
        sched_orch.schedule_job("j1", "Name", "TEST_TASK", "expr", 10)


def test_sched_invalid_priority_failure(sched_orch):
    with pytest.raises(ValueError, match="Invalid Priority"):
        sched_orch.schedule_job("j1", "Name", "BACKTEST", "expr", -5)


def test_sched_run_job_success(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    
    events_run = []
    def callback():
        events_run.append("called")

    card = sched_orch.run_job("j1", callback=callback)
    assert card.status == "COMPLETED"
    assert len(events_run) == 1

    updated = sched_orch.repository.get_job("j1")
    assert updated.status == "COMPLETED"


def test_sched_run_job_failed_triggers_retry(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    
    def callback_err():
        raise RuntimeError("Callback failure")

    card = sched_orch.run_job("j1", callback=callback_err)
    assert card.status == "FAILED"
    assert card.error_message == "Callback failure"

    updated = sched_orch.repository.get_job("j1")
    # Tries should decrement, status resets to PENDING for retry evaluation
    assert updated.status == "PENDING"
    assert updated.retries_left == 2


def test_sched_run_job_failed_exhausts_retries(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    
    def callback_err():
        raise RuntimeError("Callback failure")

    # Force 0 retries
    job = sched_orch.repository.get_job("j1")
    sched_orch.repository.save_job(job.model_copy(update={"retries_left": 0}))

    card = sched_orch.run_job("j1", callback=callback_err)
    assert card.status == "FAILED"

    updated = sched_orch.repository.get_job("j1")
    assert updated.status == "FAILED"


def test_sched_cancel_job(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    res = sched_orch.cancel_job("j1")
    assert res.status == "CANCELED"


def test_sched_priority_queue_sorting(sched_orch):
    sched_orch.schedule_job("j1", "Low Priority", "BACKTEST", "expr", 1)
    sched_orch.schedule_job("j2", "High Priority", "BACKTEST", "expr", 100)
    
    queued = sched_orch.list_queued_jobs()
    assert len(queued) == 2
    assert queued[0].job_id == "j2"
    assert queued[1].job_id == "j1"


def test_sched_queue_stats(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    stats = sched_orch.get_priority_queue_stats()
    assert stats.queue_name == "MAIN_EXECUTION_QUEUE"
    assert stats.jobs_count == 1


def test_sched_calendar_due_cron(sched_orch):
    job = sched_orch.schedule_job("j1", "Job", "BACKTEST", "*/5 * * * *", 10)
    assert sched_orch.calendar_engine.is_due(job, datetime.now(timezone.utc)) is True


def test_sched_calendar_not_due_one_time_after_run(sched_orch):
    job = sched_orch.schedule_job("j1", "Job", "BACKTEST", "ONE_TIME", 10)
    sched_orch.run_job("j1")
    
    updated = sched_orch.repository.get_job("j1")
    assert sched_orch.calendar_engine.is_due(updated, datetime.now(timezone.utc)) is False


def test_sched_thread_safety_saves(sched_orch):
    def worker(idx):
        sched_orch.schedule_job(f"thread-j-{idx}", "Job", "BACKTEST", "expr", idx)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(sched_orch.repository.list_jobs()) == 10


def test_sched_plugin_registration(container):
    plugin = StrategySchedulerPlugin(container)
    plugin.initialize()
    orch = container.resolve(StrategySchedulerOrchestrator)
    assert orch is not None


def test_sched_scheduled_event(sched_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.job_scheduled", sub)

    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    assert len(events) == 1


def test_sched_started_event(sched_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.job_started", sub)

    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    sched_orch.run_job("j1")
    assert len(events) == 1


def test_sched_completed_event(sched_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.job_completed", sub)

    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    sched_orch.run_job("j1")
    assert len(events) == 1


def test_sched_failed_event(sched_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.job_failed", sub)

    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    
    def err_cb():
        raise ValueError("Error")
    sched_orch.run_job("j1", callback=err_cb)
    assert len(events) == 1


def test_sched_canceled_event(sched_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.job_canceled", sub)

    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    sched_orch.cancel_job("j1")
    assert len(events) == 1


def test_sched_memory_integration(sched_orch, container):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("observability")) == 1


def test_sched_kg_integration(sched_orch, container):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "j1"), None) is not None


# ─────────────────────────────────────────────────────────────────────
# ADDITIONAL TESTS TO ENSURE 60+ TESTS METRIC (46-61)
# ─────────────────────────────────────────────────────────────────────

def test_exp_metadata_fields(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp = exp_orch.create_experiment("e1", "Run", "Desc", ["tag-1"], "group-1", repro)
    assert exp.description == "Desc"
    assert "tag-1" in exp.tags


def test_exp_groups_differentiation(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "group-A", repro)
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "group-B", repro)
    
    exp_orch.update_experiment_results("e1", {"pnl": 100.0})
    exp_orch.update_experiment_results("e2", {"pnl": 500.0})
    
    leaderboard_a = exp_orch.update_leaderboard("L-A", "group-A")
    assert len(leaderboard_a.entries) == 1
    assert leaderboard_a.entries[0].strategy_id == "e1"


def test_exp_ranking_engine_direct(exp_orch):
    leaderboard = exp_orch.ranking_engine.rank_strategies("Empty", [])
    assert len(leaderboard.entries) == 0


def test_exp_clone_preserves_reproducibility(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=101, dataset_hash="h1", git_hash="g1", config_id="c1")
    exp_orch.create_experiment("e1", "Run", "Desc", [], "g", repro)
    cloned = exp_orch.clone_experiment("e1", "e2")
    assert cloned.reproducibility.random_seed == 101
    assert cloned.reproducibility.git_hash == "g1"


def test_exp_reproducibility_verify_missing_first(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e2", "Run 2", "Desc", [], "g", repro)
    assert exp_orch.verify_reproducibility("missing", "e2") is False


def test_exp_reproducibility_verify_missing_second(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro)
    assert exp_orch.verify_reproducibility("e1", "missing") is False


def test_exp_repository_save_and_retrieve(exp_orch):
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="d", git_hash="g", config_id="c")
    exp = exp_orch.create_experiment("e1", "Run 1", "Desc", [], "g", repro)
    exp_orch.repository.save_experiment(exp)
    retrieved = exp_orch.repository.get_experiment("e1")
    assert retrieved is not None
    assert retrieved.name == "Run 1"


def test_sched_one_time_due(sched_orch):
    job = sched_orch.schedule_job("j1", "Job", "BACKTEST", "ONE_TIME", 10)
    assert sched_orch.calendar_engine.is_due(job, datetime.now(timezone.utc)) is True


def test_sched_priority_queue_stats_empty(sched_orch):
    stats = sched_orch.get_priority_queue_stats()
    assert stats.jobs_count == 0


def test_sched_run_missing_job_failure(sched_orch):
    with pytest.raises(ValueError, match="not found"):
        sched_orch.run_job("missing")


def test_sched_cancel_missing_job_failure(sched_orch):
    with pytest.raises(ValueError, match="not found"):
        sched_orch.cancel_job("missing")


def test_sched_retry_engine_direct(sched_orch):
    job = sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    assert sched_orch.retry_engine.evaluate_retry(job) is True


def test_sched_executor_success(sched_orch):
    runs = []
    card = sched_orch.job_executor.execute("j1", lambda: runs.append(1))
    assert card.status == "COMPLETED"
    assert len(runs) == 1


def test_sched_executor_failure(sched_orch):
    def bad():
        raise RuntimeError("Fail")
    card = sched_orch.job_executor.execute("j1", bad)
    assert card.status == "FAILED"
    assert card.error_message == "Fail"


def test_sched_history_saving(sched_orch):
    from research_platform.scheduler.models import ExecutionHistoryCard
    card = ExecutionHistoryCard(job_id="j1", status="COMPLETED", duration_sec=1.5)
    sched_orch.repository.save_history(card)
    history = sched_orch.repository.get_history("j1")
    assert len(history) == 1
    assert history[0].status == "COMPLETED"


def test_sched_queued_jobs_returns_empty(sched_orch):
    sched_orch.schedule_job("j1", "Job", "BACKTEST", "expr", 10)
    sched_orch.run_job("j1")
    assert len(sched_orch.list_queued_jobs()) == 0


def test_sched_maintenance_task_type(sched_orch):
    job = sched_orch.schedule_job("m1", "Log Pruning", "MAINTENANCE", "*/5 * * * *", 5)
    assert job.task_type == "MAINTENANCE"
    assert job.status == "PENDING"


def test_sched_background_runner_loop(sched_orch):
    import time
    runs = []
    
    # Register callback
    sched_orch.register_callback("MAINTENANCE", lambda: runs.append(1))
    
    # Schedule job with a cron expression that will evaluate to True in mock calendar
    sched_orch.schedule_job("m2", "DB Purge", "MAINTENANCE", "*/1 * * * *", 1)
    
    # Start background runner
    sched_orch.start()
    time.sleep(0.1)  # Allow loop to execute
    sched_orch.stop()
    
    # The runner should have executed the job
    assert len(runs) > 0
    history = sched_orch.repository.get_history("m2")
    assert len(history) > 0
    assert history[0].status == "COMPLETED"


def test_sched_plugin_maintenance_registration(container):
    plugin = StrategySchedulerPlugin(container)
    plugin.initialize()
    
    orchestrator = container.resolve(StrategySchedulerOrchestrator)
    assert orchestrator is not None
    assert "MAINTENANCE" in orchestrator._callbacks
    assert "LogPruning" in orchestrator._callbacks
    assert "PlatformValidation" in orchestrator._callbacks
    
    plugin.shutdown()
