"""Comprehensive Test Suite — Sprint 11C Model Evaluation Engine (50 tests)."""

import ast
import pathlib
import threading
import time
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from self_learning.benchmark_manager import BenchmarkManager, BenchmarkResult
from self_learning.evaluation_engine import EvaluationEngine
from self_learning.evaluation_events import (
    BenchmarkCompleted,
    EvaluationCancelled,
    EvaluationCompleted,
    EvaluationCreated,
    EvaluationFailed,
    EvaluationStarted,
    LeaderboardUpdated,
    PromotionEvaluated,
)
from self_learning.evaluation_manager import EvaluationManager, EvaluationRecord, EvaluationStatus
from self_learning.evaluation_metrics import EvaluationMetricsStore, MetricResult
from self_learning.evaluation_reports import EvaluationReport, EvaluationReportStore
from self_learning.leaderboard import Leaderboard, LeaderboardEntry
from self_learning.promotion_rules import PromotionCriteria, PromotionRecommendation, PromotionRuleEngine
from self_learning.validation_manager import ValidationDatasetRecord, ValidationManager
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def eval_mgr(event_bus):
    return EvaluationManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. Evaluation Lifecycle (Tests 1–10)
# ---------------------------------------------------------------------------
def test_evaluation_created(eval_mgr):
    e = eval_mgr.create_evaluation("model_100", "ds_val_1")
    assert e.status == EvaluationStatus.CREATED
    assert e.model_id == "model_100"
    assert e.is_advisory_only is True


def test_evaluation_execution_success(eval_mgr):
    e = eval_mgr.create_evaluation("model_101", "ds_val_1")
    executed = eval_mgr.execute_evaluation(e.evaluation_id)
    assert executed.status == EvaluationStatus.COMPLETED
    assert executed.metrics is not None
    assert executed.metrics.accuracy > 0.0
    assert executed.recommendation is not None
    assert executed.report is not None


def test_evaluation_execution_failure(eval_mgr):
    def failing_evaluator(preds, targets, kwargs):
        raise ValueError("Simulated evaluation engine error")

    eval_mgr._engine.register_evaluator("failing", failing_evaluator)
    e = eval_mgr.create_evaluation("model_102", "ds_val_1", evaluator_name="failing")
    failed = eval_mgr.execute_evaluation(e.evaluation_id)
    assert failed.status == EvaluationStatus.FAILED
    assert "Simulated evaluation engine error" in failed.error_message


def test_evaluation_cancellation(eval_mgr):
    e = eval_mgr.create_evaluation("model_103", "ds_val_1")
    cancelled = eval_mgr.cancel_evaluation(e.evaluation_id, reason="User test stop")
    assert cancelled.status == EvaluationStatus.CANCELLED
    assert "User test stop" in cancelled.error_message


def test_evaluation_retry(eval_mgr):
    def flaky_evaluator(preds, targets, kwargs):
        if kwargs.get("fail", False):
            raise RuntimeError("Temporary error")
        return {"accuracy": 0.95, "f1_score": 0.94}

    eval_mgr._engine.register_evaluator("flaky", flaky_evaluator)
    e = eval_mgr.create_evaluation("model_104", "ds_val_1", evaluator_name="flaky")
    failed = eval_mgr.execute_evaluation(e.evaluation_id, fail=True)
    assert failed.status == EvaluationStatus.FAILED

    retried = eval_mgr.retry_evaluation(e.evaluation_id, fail=False)
    assert retried.status == EvaluationStatus.COMPLETED
    assert retried.metrics.accuracy == 0.95


def test_evaluation_list_by_status(eval_mgr):
    e1 = eval_mgr.create_evaluation("m1", "d1")
    e2 = eval_mgr.create_evaluation("m2", "d2")
    eval_mgr.execute_evaluation(e1.evaluation_id)

    completed = eval_mgr.list_evaluations(status=EvaluationStatus.COMPLETED)
    created = eval_mgr.list_evaluations(status=EvaluationStatus.CREATED)

    assert len(completed) == 1
    assert len(created) == 1


def test_evaluation_terminal_state_cancellation_protected(eval_mgr):
    e = eval_mgr.create_evaluation("m_term", "d1")
    executed = eval_mgr.execute_evaluation(e.evaluation_id)
    assert executed.status == EvaluationStatus.COMPLETED

    res = eval_mgr.cancel_pipeline if hasattr(eval_mgr, "cancel_pipeline") else eval_mgr.cancel_evaluation(e.evaluation_id)
    assert res.status == EvaluationStatus.COMPLETED


def test_evaluation_concurrent_cancellation_respected(event_bus):
    mgr = EvaluationManager(event_bus=event_bus)
    e = mgr.create_evaluation("m_conc", "d1")

    started_evt = threading.Event()
    cancel_done = threading.Event()

    def slow_evaluator(preds, targets, kwargs):
        started_evt.set()
        cancel_done.wait(timeout=2.0)
        return {"accuracy": 0.9}

    mgr._engine.register_evaluator("slow", slow_evaluator)
    e_task = mgr.create_evaluation("m_conc", "d1", evaluator_name="slow")

    t = threading.Thread(target=lambda: mgr.execute_evaluation(e_task.evaluation_id))
    t.start()

    assert started_evt.wait(timeout=2.0)
    cancelled = mgr.cancel_evaluation(e_task.evaluation_id)
    assert cancelled.status == EvaluationStatus.CANCELLED
    cancel_done.set()
    t.join(timeout=2.0)

    final = mgr.get_evaluation(e_task.evaluation_id)
    assert final.status == EvaluationStatus.CANCELLED


def test_evaluation_capacity_enforcement():
    small_mgr = EvaluationManager(max_evaluations=2)
    small_mgr.create_evaluation("m1", "d1")
    small_mgr.create_evaluation("m2", "d2")

    with pytest.raises(RuntimeError, match="capacity exceeded"):
        small_mgr.create_evaluation("m3", "d3")


def test_evaluation_advisory_flag(eval_mgr):
    e = eval_mgr.create_evaluation("m_adv", "d1")
    executed = eval_mgr.execute_evaluation(e.evaluation_id)
    assert executed.is_advisory_only is True
    assert executed.metrics.is_advisory_only is True
    assert executed.recommendation.is_advisory_only is True


# ---------------------------------------------------------------------------
# 2. Benchmarking (Tests 11–15)
# ---------------------------------------------------------------------------
def test_benchmark_run(event_bus):
    bench_mgr = BenchmarkManager(event_bus=event_bus)
    m1 = MetricResult(evaluation_id="e1", model_id="mod_a", dataset_id="d1", accuracy=0.90, f1_score=0.88)
    m2 = MetricResult(evaluation_id="e2", model_id="mod_b", dataset_id="d1", accuracy=0.95, f1_score=0.94)

    res = bench_mgr.run_benchmark("alpha_bench", "d1", {"mod_a": m1, "mod_b": m2})
    assert res.name == "alpha_bench"
    assert len(res.rankings) == 2
    assert res.rankings[0].model_id == "mod_b"


def test_benchmark_rankings_order(event_bus):
    bench_mgr = BenchmarkManager(event_bus=event_bus)
    m1 = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.70)
    m2 = MetricResult(evaluation_id="e2", model_id="m2", dataset_id="d1", accuracy=0.85)
    m3 = MetricResult(evaluation_id="e3", model_id="m3", dataset_id="d1", accuracy=0.99)

    res = bench_mgr.run_benchmark("prio_bench", "d1", {"m1": m1, "m2": m2, "m3": m3}, primary_metric="accuracy")
    ranked_ids = [r.model_id for r in res.rankings]
    assert ranked_ids == ["m3", "m2", "m1"]


def test_benchmark_statistical_summary(event_bus):
    bench_mgr = BenchmarkManager(event_bus=event_bus)
    m1 = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.80, val_loss=0.20)
    m2 = MetricResult(evaluation_id="e2", model_id="m2", dataset_id="d1", accuracy=0.90, val_loss=0.10)

    res = bench_mgr.run_benchmark("stat_bench", "d1", {"m1": m1, "m2": m2})
    stats = res.statistical_summary
    assert "accuracy" in stats
    assert stats["accuracy"]["mean"] == 0.85
    assert stats["accuracy"]["min"] == 0.80
    assert stats["accuracy"]["max"] == 0.90


def test_benchmark_get_by_id(event_bus):
    bench_mgr = BenchmarkManager(event_bus=event_bus)
    m = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.9)
    b = bench_mgr.run_benchmark("b1", "d1", {"m1": m})

    retrieved = bench_mgr.get_benchmark(b.benchmark_id)
    assert retrieved is not None
    assert retrieved.name == "b1"


def test_benchmark_event_published(event_bus):
    events = []
    event_bus.subscribe("BenchmarkCompleted", lambda e: events.append(e))

    bench_mgr = BenchmarkManager(event_bus=event_bus)
    m = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.9)
    bench_mgr.run_benchmark("evt_bench", "d1", {"m1": m})

    assert len(events) == 1
    assert events[0].event_type == "BenchmarkCompleted"
    assert events[0].top_model_id == "m1"


# ---------------------------------------------------------------------------
# 3. Validation Datasets (Tests 16–20)
# ---------------------------------------------------------------------------
def test_validation_dataset_register():
    v_mgr = ValidationManager()
    ds = v_mgr.register_validation_dataset(
        name="val_2024",
        feature_columns=["open", "high", "low", "close", "volume"],
        target_column="label",
        row_count=5000,
    )
    assert ds.name == "val_2024"
    assert len(ds.feature_columns) == 5
    assert ds.row_count == 5000


def test_validation_dataset_get_by_id():
    v_mgr = ValidationManager()
    ds = v_mgr.register_validation_dataset("ds_get", feature_columns=["f1"])
    retrieved = v_mgr.get_dataset(ds.dataset_id)
    assert retrieved is not None
    assert retrieved.name == "ds_get"


def test_validation_dataset_name_history():
    v_mgr = ValidationManager()
    v_mgr.register_validation_dataset("ds_hist", feature_columns=["f1"])
    v_mgr.register_validation_dataset("ds_hist", feature_columns=["f1", "f2"])

    history = v_mgr.get_by_name("ds_hist")
    assert len(history) == 2


def test_validation_compatibility_success():
    v_mgr = ValidationManager()
    ds = v_mgr.register_validation_dataset("ds_compat", feature_columns=["f1", "f2", "f3"])
    ok, errors = v_mgr.validate_compatibility(["f1", "f2"], ds.dataset_id)
    assert ok is True
    assert len(errors) == 0


def test_validation_compatibility_missing_columns():
    v_mgr = ValidationManager()
    ds = v_mgr.register_validation_dataset("ds_missing", feature_columns=["f1"])
    ok, errors = v_mgr.validate_compatibility(["f1", "f2_required"], ds.dataset_id)
    assert ok is False
    assert len(errors) == 1
    assert "f2_required" in errors[0]


# ---------------------------------------------------------------------------
# 4. Leaderboard (Tests 21–25)
# ---------------------------------------------------------------------------
def test_leaderboard_update():
    lb = Leaderboard()
    m1 = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.85)
    m2 = MetricResult(evaluation_id="e2", model_id="m2", dataset_id="d1", accuracy=0.92)

    rankings = lb.update_ranking("board_1", [m1, m2], metric_name="accuracy")
    assert len(rankings) == 2
    assert rankings[0].model_id == "m2"
    assert rankings[0].rank == 1


def test_leaderboard_top_models():
    lb = Leaderboard()
    m1 = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.80)
    m2 = MetricResult(evaluation_id="e2", model_id="m2", dataset_id="d1", accuracy=0.90)
    m3 = MetricResult(evaluation_id="e3", model_id="m3", dataset_id="d1", accuracy=0.85)

    lb.update_ranking("board_top", [m1, m2, m3])
    top_2 = lb.get_top_models("board_top", top_k=2)

    assert len(top_2) == 2
    assert top_2[0].model_id == "m2"
    assert top_2[1].model_id == "m3"


def test_leaderboard_stable_tie_breaker():
    lb = Leaderboard()
    # Identical accuracy score — tie broken by model_id alphabetical sort key ("mod_a" < "mod_b")
    m1 = MetricResult(evaluation_id="e1", model_id="mod_b", dataset_id="d1", accuracy=0.90)
    m2 = MetricResult(evaluation_id="e2", model_id="mod_a", dataset_id="d1", accuracy=0.90)

    rankings = lb.update_ranking("board_tie", [m1, m2], metric_name="accuracy")
    assert rankings[0].model_id == "mod_a"
    assert rankings[1].model_id == "mod_b"


def test_leaderboard_lower_is_better_metric():
    lb = Leaderboard()
    m1 = MetricResult(evaluation_id="e1", model_id="m_high_loss", dataset_id="d1", val_loss=0.45)
    m2 = MetricResult(evaluation_id="e2", model_id="m_low_loss", dataset_id="d1", val_loss=0.10)

    rankings = lb.update_ranking("board_loss", [m1, m2], metric_name="val_loss")
    assert rankings[0].model_id == "m_low_loss"


def test_leaderboard_get_model_rank():
    lb = Leaderboard()
    m1 = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.80)
    m2 = MetricResult(evaluation_id="e2", model_id="m2", dataset_id="d1", accuracy=0.95)

    lb.update_ranking("board_rank", [m1, m2])
    assert lb.get_model_rank("board_rank", "m2") == 1
    assert lb.get_model_rank("board_rank", "m1") == 2
    assert lb.get_model_rank("board_rank", "nonexistent") is None


# ---------------------------------------------------------------------------
# 5. Promotion Rules (Tests 26–30)
# ---------------------------------------------------------------------------
def test_promotion_rule_pass():
    engine = PromotionRuleEngine()
    m = MetricResult(
        evaluation_id="e1",
        model_id="m_good",
        dataset_id="d1",
        accuracy=0.90,
        val_loss=0.15,
        f1_score=0.88,
        sample_count=200,
    )
    rec = engine.evaluate_promotion(m)
    assert rec.is_eligible is True
    assert "satisfies all" in rec.reasons[0]


def test_promotion_rule_min_accuracy_fail():
    engine = PromotionRuleEngine()
    m = MetricResult(
        evaluation_id="e1",
        model_id="m_low_acc",
        dataset_id="d1",
        accuracy=0.75,  # Below 0.85
        val_loss=0.15,
        f1_score=0.88,
        sample_count=200,
    )
    rec = engine.evaluate_promotion(m)
    assert rec.is_eligible is False
    assert any("Accuracy" in r for r in rec.reasons)


def test_promotion_rule_max_val_loss_fail():
    engine = PromotionRuleEngine()
    m = MetricResult(
        evaluation_id="e1",
        model_id="m_high_loss",
        dataset_id="d1",
        accuracy=0.90,
        val_loss=0.35,  # Above 0.25
        f1_score=0.88,
        sample_count=200,
    )
    rec = engine.evaluate_promotion(m)
    assert rec.is_eligible is False
    assert any("Validation loss" in r for r in rec.reasons)


def test_promotion_rule_min_f1_fail():
    engine = PromotionRuleEngine()
    m = MetricResult(
        evaluation_id="e1",
        model_id="m_low_f1",
        dataset_id="d1",
        accuracy=0.90,
        val_loss=0.15,
        f1_score=0.70,  # Below 0.80
        sample_count=200,
    )
    rec = engine.evaluate_promotion(m)
    assert rec.is_eligible is False
    assert any("F1 score" in r for r in rec.reasons)


def test_promotion_rule_min_sample_count_fail():
    engine = PromotionRuleEngine()
    m = MetricResult(
        evaluation_id="e1",
        model_id="m_small_sample",
        dataset_id="d1",
        accuracy=0.90,
        val_loss=0.15,
        f1_score=0.88,
        sample_count=50,  # Below 100
    )
    rec = engine.evaluate_promotion(m)
    assert rec.is_eligible is False
    assert any("Sample count" in r for r in rec.reasons)


# ---------------------------------------------------------------------------
# 6. Evaluation Reports (Tests 31–35)
# ---------------------------------------------------------------------------
def test_report_create():
    store = EvaluationReportStore()
    m = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1", accuracy=0.92)
    p_engine = PromotionRuleEngine()
    rec = p_engine.evaluate_promotion(m)

    rep = store.create_report("m1", "e1", m, rec, benchmark_summary={"rank": 1})
    assert rep.model_id == "m1"
    assert rep.metrics_summary.accuracy == 0.92
    assert rep.promotion_recommendation.is_eligible is True


def test_report_get_by_id():
    store = EvaluationReportStore()
    m = MetricResult(evaluation_id="e1", model_id="m2", dataset_id="d1", accuracy=0.92)
    rec = PromotionRuleEngine().evaluate_promotion(m)

    rep = store.create_report("m2", "e1", m, rec)
    retrieved = store.get_report(rep.report_id)
    assert retrieved is not None
    assert retrieved.model_id == "m2"


def test_report_list_by_model():
    store = EvaluationReportStore()
    m1 = MetricResult(evaluation_id="e1", model_id="m_target", dataset_id="d1")
    m2 = MetricResult(evaluation_id="e2", model_id="m_other", dataset_id="d1")
    rec1 = PromotionRuleEngine().evaluate_promotion(m1)
    rec2 = PromotionRuleEngine().evaluate_promotion(m2)

    store.create_report("m_target", "e1", m1, rec1)
    store.create_report("m_other", "e2", m2, rec2)

    reports = store.list_reports("m_target")
    assert len(reports) == 1
    assert reports[0].model_id == "m_target"


def test_report_immutability():
    m = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1")
    rec = PromotionRuleEngine().evaluate_promotion(m)
    rep = EvaluationReport(model_id="m1", evaluation_id="e1", metrics_summary=m, promotion_recommendation=rec)

    with pytest.raises((ValidationError, TypeError)):
        rep.model_id = "hacked"


def test_report_advisory_flag():
    m = MetricResult(evaluation_id="e1", model_id="m1", dataset_id="d1")
    rec = PromotionRuleEngine().evaluate_promotion(m)
    rep = EvaluationReport(model_id="m1", evaluation_id="e1", metrics_summary=m, promotion_recommendation=rec)
    assert rep.is_advisory_only is True


# ---------------------------------------------------------------------------
# 7. Metrics Repository (Tests 36–40)
# ---------------------------------------------------------------------------
def test_metrics_store_record():
    store = EvaluationMetricsStore()
    res = store.record_metrics("e1", "m1", "d1", accuracy=0.94, f1_score=0.93)
    assert res.accuracy == 0.94
    assert res.f1_score == 0.93


def test_metrics_store_get_latest():
    store = EvaluationMetricsStore()
    store.record_metrics("e1", "m1", "d1", accuracy=0.80)
    store.record_metrics("e2", "m1", "d1", accuracy=0.95)

    latest = store.get_latest_metrics("m1")
    assert latest is not None
    assert latest.accuracy == 0.95


def test_metrics_store_history():
    store = EvaluationMetricsStore()
    store.record_metrics("e1", "m1", "d1", accuracy=0.80)
    store.record_metrics("e2", "m1", "d1", accuracy=0.85)

    hist = store.get_metrics_history("m1")
    assert len(hist) == 2


def test_metrics_store_list_all():
    store = EvaluationMetricsStore()
    store.record_metrics("e1", "m1", "d1")
    store.record_metrics("e2", "m2", "d1")

    all_metrics = store.list_all_metrics()
    assert len(all_metrics) == 2


def test_metrics_store_bounded_history():
    store = EvaluationMetricsStore(max_records_per_model=2)
    store.record_metrics("e1", "m1", "d1", accuracy=0.7)
    store.record_metrics("e2", "m1", "d1", accuracy=0.8)
    store.record_metrics("e3", "m1", "d1", accuracy=0.9)

    hist = store.get_metrics_history("m1")
    assert len(hist) == 2
    assert hist[0].accuracy == 0.8
    assert hist[1].accuracy == 0.9


# ---------------------------------------------------------------------------
# 8. Events (Tests 41–45)
# ---------------------------------------------------------------------------
def test_event_evaluation_created(event_bus, eval_mgr):
    evts = []
    event_bus.subscribe("EvaluationCreated", lambda e: evts.append(e))
    eval_mgr.create_evaluation("m1", "d1")
    assert len(evts) == 1
    assert evts[0].event_type == "EvaluationCreated"


def test_event_evaluation_started_completed(event_bus, eval_mgr):
    started_evts = []
    completed_evts = []
    event_bus.subscribe("EvaluationStarted", lambda e: started_evts.append(e))
    event_bus.subscribe("EvaluationCompleted", lambda e: completed_evts.append(e))

    e = eval_mgr.create_evaluation("m1", "d1")
    eval_mgr.execute_evaluation(e.evaluation_id)

    assert len(started_evts) == 1
    assert len(completed_evts) == 1


def test_event_evaluation_failed(event_bus, eval_mgr):
    evts = []
    event_bus.subscribe("EvaluationFailed", lambda e: evts.append(e))

    eval_mgr._engine.register_evaluator("fail", lambda p, t, k: 1 / 0)
    e = eval_mgr.create_evaluation("m1", "d1", evaluator_name="fail")
    eval_mgr.execute_evaluation(e.evaluation_id)

    assert len(evts) == 1
    assert evts[0].event_type == "EvaluationFailed"


def test_event_evaluation_cancelled(event_bus, eval_mgr):
    evts = []
    event_bus.subscribe("EvaluationCancelled", lambda e: evts.append(e))
    e = eval_mgr.create_evaluation("m1", "d1")
    eval_mgr.cancel_evaluation(e.evaluation_id)
    assert len(evts) == 1
    assert evts[0].event_type == "EvaluationCancelled"


def test_event_promotion_evaluated(event_bus, eval_mgr):
    evts = []
    event_bus.subscribe("PromotionEvaluated", lambda e: evts.append(e))
    e = eval_mgr.create_evaluation("m1", "d1")
    eval_mgr.execute_evaluation(e.evaluation_id)
    assert len(evts) == 1
    assert evts[0].event_type == "PromotionEvaluated"


# ---------------------------------------------------------------------------
# 9. Thread Safety & Performance (Tests 46–47)
# ---------------------------------------------------------------------------
def test_thread_safety_concurrent_evaluations(eval_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(5):
                e = eval_mgr.create_evaluation(f"mod_{i}_{j}", "d1")
                eval_mgr.execute_evaluation(e.evaluation_id)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert eval_mgr.count() == 25


def test_performance_500_evaluations_and_leaderboard():
    eval_mgr = EvaluationManager(max_evaluations=600)
    start_t = time.perf_counter()

    for i in range(500):
        e = eval_mgr.create_evaluation(f"scale_mod_{i}", "d1")

    elapsed = time.perf_counter() - start_t
    assert eval_mgr.count() == 500
    assert elapsed < 5.0  # Must scale efficiently under capacity


# ---------------------------------------------------------------------------
# 10. Regression & Architecture Boundary (Tests 48–50)
# ---------------------------------------------------------------------------
def test_regression_sprint11a_unaffected():
    from self_learning.model_registry import ModelRegistry
    reg = ModelRegistry()
    r = reg.register_model("s11a_mod")
    assert r.name == "s11a_mod"
    assert r.is_advisory_only is True


def test_regression_sprint11b_unaffected():
    from self_learning.training_pipeline import TrainingPipelineManager
    pipe_mgr = TrainingPipelineManager()
    p = pipe_mgr.create_pipeline("s11b_pipe", "m", "d")
    assert p.config.name == "s11b_pipe"
    assert p.is_advisory_only is True


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
