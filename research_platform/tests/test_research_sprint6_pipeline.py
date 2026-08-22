"""Integration tests for Sprint 6 Research Platform components, pipeline execution, and plugin lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from research_platform.analysis.dashboard_backend import ResearchDashboardBackend
from research_platform.analysis.dataset_manager import DatasetManager
from research_platform.analysis.feature_importance_engine import FeatureImportanceEngine
from research_platform.analysis.metrics_engine import MetricsEngine
from research_platform.analysis.parameter_sweep_engine import ParameterSweepEngine
from research_platform.analysis.report_generator import ReportGenerator
from research_platform.analysis.strategy_registry import StrategyRegistry
from research_platform.analysis.walk_forward_engine import WalkForwardFramework
from research_platform.core.enums import ExperimentStatus, ReportFormat, SweepMethod
from research_platform.core.events import (
    ExperimentCompleted,
    ExperimentCreated,
    ExperimentStarted,
    ResearchPlatformInitialized,
    ResearchPlatformShutdown,
)
from research_platform.core.models import (
    DatasetVersion,
    ExperimentConfig,
    ExperimentResult,
    ParameterSweepConfig,
    PerformanceMetrics,
    StrategyVersion,
)
from research_platform.core.orchestrator import ResearchOrchestrator
from research_platform.core.plugin import ResearchPlatformPlugin
from research_platform.core.repository import ResearchExperimentRepository
from research_platform.core.state import ResearchStateStore
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.types import HealthStatus, ModuleState


def test_dataset_manager_and_strategy_registry_crud():
    """Verify registration, lookup, and version management in dataset manager and strategy registry."""
    dm = DatasetManager()
    ds1 = DatasetVersion(
        dataset_id="ds-btc",
        name="BTC 1h",
        version="v1.0.0",
        checksum="chk-1",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        record_count=100,
    )
    dm.register_dataset(ds1)

    assert dm.get_dataset("ds-btc") == ds1
    assert dm.get_dataset("ds-btc", "v1.0.0") == ds1
    assert len(dm.list_datasets()) == 1

    sr = StrategyRegistry()
    st1 = StrategyVersion(
        strategy_id="strat-sma",
        name="SMA Cross",
        version="v1.0.0",
    )
    sr.register_strategy(st1)

    assert sr.get_strategy("strat-sma") == st1
    assert sr.get_strategy("strat-sma", "v1.0.0") == st1
    assert len(sr.list_strategies()) == 1


def test_metrics_engine_calculations():
    """Verify quantitative metrics engine calculation accuracy."""
    me = MetricsEngine()
    returns = [0.02, -0.01, 0.03, 0.015, -0.005, 0.025]
    metrics = me.calculate_metrics(returns)

    assert metrics.sharpe_ratio > 0.0
    assert metrics.win_rate > 0.6
    assert metrics.profit_factor > 1.0
    assert metrics.total_trades == 6
    assert metrics.winning_trades == 4
    assert metrics.losing_trades == 2


def test_feature_importance_engine():
    """Verify feature importance permutation/correlation scoring."""
    fie = FeatureImportanceEngine()
    feature_matrix = [
        {"trend_strength": 0.8, "rsi": 70.0, "volume_surge": 1.5},
        {"trend_strength": 0.2, "rsi": 30.0, "volume_surge": 0.8},
        {"trend_strength": 0.9, "rsi": 75.0, "volume_surge": 2.0},
        {"trend_strength": 0.1, "rsi": 25.0, "volume_surge": 0.5},
    ]
    target_returns = [0.03, -0.02, 0.04, -0.03]

    res = fie.calculate_importance("exp-feat-1", feature_matrix, target_returns)

    assert len(res.features) == 3
    assert res.features[0].rank == 1
    assert res.features[0].importance_score >= res.features[1].importance_score


def test_parameter_sweep_engine():
    """Verify parameter sweep optimization engine execution."""
    pse = ParameterSweepEngine()
    cfg = ParameterSweepConfig(
        sweep_id="sweep-001",
        method=SweepMethod.GRID,
        parameter_ranges={"fast": [5, 10, 15], "slow": [20, 30, 40]},
        max_iterations=10,
    )

    def dummy_eval(params: dict) -> PerformanceMetrics:
        # Mock Sharpe ratio proportional to slow - fast gap
        sharpe = float(params["slow"] - params["fast"]) / 10.0
        return PerformanceMetrics(sharpe_ratio=sharpe)

    res = pse.run_sweep(dummy_eval, cfg)

    assert res.sweep_id == "sweep-001"
    assert len(res.trials) == 9
    assert res.best_parameters == {"fast": 5, "slow": 40}
    assert res.best_metrics.sharpe_ratio == 3.5


def test_walk_forward_framework():
    """Verify walk-forward out-of-sample window evaluation."""
    wff = WalkForwardFramework()
    ds = DatasetVersion(
        dataset_id="ds-wf-1",
        name="WalkForward DS",
        version="v1.0.0",
        checksum="chk-wf",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 31, tzinfo=timezone.utc),
        record_count=365,
    )

    def dummy_eval(dataset_part: DatasetVersion, params: dict) -> PerformanceMetrics:
        # Return deterministic Sharpe based on start_time
        day = dataset_part.start_time.day
        return PerformanceMetrics(sharpe_ratio=1.5 + (day % 3) * 0.1)

    res = wff.evaluate(dummy_eval, ds, {}, train_window_ratio=0.7, num_windows=4)

    assert len(res.windows) == 4
    assert res.average_efficiency > 0.0
    assert res.stability_score >= 0.0


def test_report_generator_formats():
    """Verify report generator produces valid Markdown, JSON, and PDF documents."""
    rg = ReportGenerator()
    ds = DatasetVersion(dataset_id="ds-rpt", name="Rpt DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-rpt", name="Rpt Strat", version="v1")
    cfg = ExperimentConfig(experiment_id="exp-rpt-1", name="Report Experiment", dataset_version=ds, strategy_version=st)
    exp = ExperimentResult(experiment_id="exp-rpt-1", config=cfg, status=ExperimentStatus.COMPLETED, metrics=PerformanceMetrics(sharpe_ratio=2.1), completed_at=datetime.now(timezone.utc))

    md_rpt = rg.generate_report(exp, ReportFormat.MARKDOWN)
    assert "# Research Experiment Report" in md_rpt.content
    assert "2.1000" in md_rpt.content

    json_rpt = rg.generate_report(exp, ReportFormat.JSON)
    assert '"experiment_id": "exp-rpt-1"' in json_rpt.content

    pdf_rpt = rg.generate_report(exp, ReportFormat.PDF)
    assert "%PDF-1.4" in pdf_rpt.content


def test_dashboard_backend_aggregation():
    """Verify research dashboard backend builds visualization state."""
    repo = ResearchExperimentRepository()
    ds = DatasetVersion(dataset_id="ds-dash", name="Dash DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-dash", name="Dash Strat", version="v1")
    cfg = ExperimentConfig(experiment_id="exp-dash-1", name="Dash Exp", dataset_version=ds, strategy_version=st)
    exp = ExperimentResult(experiment_id="exp-dash-1", config=cfg, status=ExperimentStatus.COMPLETED, metrics=PerformanceMetrics(sharpe_ratio=2.5), completed_at=datetime.now(timezone.utc))

    repo.save_experiment(exp)

    db = ResearchDashboardBackend(repo)
    view = db.build_dashboard_view()

    assert view.experiment_count == 1
    assert len(view.top_experiments) == 1
    assert view.metric_summaries["avg_sharpe_ratio"] == 2.5


def test_orchestrator_full_workflow_and_event_bus():
    """Verify orchestrator runs full experiment workflow and dispatches event bus events."""
    bus = InMemoryEventBus()
    events = []
    bus.subscribe("system.experiment_created", lambda e: events.append(("created", e)))
    bus.subscribe("system.experiment_started", lambda e: events.append(("started", e)))
    bus.subscribe("system.experiment_completed", lambda e: events.append(("completed", e)))
    bus.subscribe("system.report_generated", lambda e: events.append(("report", e)))

    orch = ResearchOrchestrator()
    orch.initialize(event_bus=bus)

    ds = DatasetVersion(
        dataset_id="ds-orch-1",
        name="Orch Dataset",
        version="v1.0.0",
        checksum="orch-checksum",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        record_count=50,
    )
    strat = StrategyVersion(
        strategy_id="strat-orch-1",
        name="Orch Strategy",
        version="v1.0.0",
    )

    cfg = orch.create_experiment("Full Workflow Test", ds, strat, parameters={"returns": [0.01, -0.005, 0.02, 0.015, -0.01], "sample_features": [{"f1": 0.5}, {"f1": 0.8}]})
    res = orch.run_experiment(cfg)

    assert res.status == ExperimentStatus.COMPLETED
    assert res.metrics.sharpe_ratio != 0.0
    assert res.feature_importance is not None
    assert any(e[0] == "created" for e in events)
    assert any(e[0] == "started" for e in events)
    assert any(e[0] == "completed" for e in events)
    assert any(e[0] == "report" for e in events)


def test_plugin_lifecycle_and_di_wiring():
    """Verify plugin initialization, container binding, health check, and shutdown."""
    bus = InMemoryEventBus()
    container_mock = MagicMock()
    container_mock.has.return_value = False

    plugin = ResearchPlatformPlugin(event_bus=bus, container=container_mock)

    assert plugin.plugin_id == "research_platform"
    assert plugin.state == ModuleState.CREATED

    plugin.initialize()

    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY
    assert container_mock.register.called

    plugin.shutdown()

    assert plugin.state == ModuleState.STOPPED
