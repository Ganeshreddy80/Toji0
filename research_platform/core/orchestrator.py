"""Research Orchestrator managing experiment execution, data/strategy lookup, metrics calculation, and event bus broadcasts."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from research_platform.analysis.dashboard_backend import ResearchDashboardBackend
from research_platform.analysis.dataset_manager import DatasetManager
from research_platform.analysis.feature_importance_engine import FeatureImportanceEngine
from research_platform.analysis.metrics_engine import MetricsEngine
from research_platform.analysis.parameter_sweep_engine import ParameterSweepEngine
from research_platform.analysis.report_generator import ReportGenerator
from research_platform.analysis.strategy_registry import StrategyRegistry
from research_platform.analysis.walk_forward_engine import WalkForwardFramework
from research_platform.core.enums import ExperimentStatus, ReportFormat
from research_platform.core.events import (
    ExperimentCompleted,
    ExperimentCreated,
    ExperimentFailed,
    ExperimentStarted,
    ParameterSweepCompleted,
    ReportGenerated,
    WalkForwardCompleted,
)
from research_platform.core.exceptions import OrchestratorError
from research_platform.core.interfaces import (
    IDatasetManager,
    IExperimentManager,
    IExperimentRepository,
    IFeatureImportanceEngine,
    IMetricsEngine,
    IParameterSweepEngine,
    IReportGenerator,
    IResearchDashboardBackend,
    IStrategyRegistry,
    IWalkForwardFramework,
)
from research_platform.core.models import (
    DatasetVersion,
    ExperimentConfig,
    ExperimentResult,
    FeatureImportanceResult,
    ParameterSweepConfig,
    ParameterSweepResult,
    PerformanceMetrics,
    ResearchDashboardView,
    ResearchManifest,
    ResearchReport,
    StrategyVersion,
    WalkForwardResult,
)
from research_platform.core.repository import ResearchExperimentRepository
from research_platform.core.state import ResearchStateStore
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class ResearchOrchestrator(IExperimentManager):
    """Authoritative coordinator executing research experiments, managing fail-closed state, persistence, and event dispatch."""

    def __init__(self) -> None:
        self._dataset_manager: IDatasetManager = DatasetManager()
        self._strategy_registry: IStrategyRegistry = StrategyRegistry()
        self._metrics_engine: IMetricsEngine = MetricsEngine()
        self._walk_forward_engine: IWalkForwardFramework = WalkForwardFramework()
        self._feature_engine: IFeatureImportanceEngine = FeatureImportanceEngine()
        self._sweep_engine: IParameterSweepEngine = ParameterSweepEngine()
        self._report_generator: IReportGenerator = ReportGenerator()
        self._state_store: ResearchStateStore = ResearchStateStore()
        self._repository: IExperimentRepository = ResearchExperimentRepository()
        self._event_bus: Optional[IEventBus] = None
        self._container: Optional[IContainer] = None
        self._dashboard_backend: IResearchDashboardBackend = ResearchDashboardBackend(self._repository)

    def initialize(
        self,
        dataset_manager: Optional[IDatasetManager] = None,
        strategy_registry: Optional[IStrategyRegistry] = None,
        metrics_engine: Optional[IMetricsEngine] = None,
        walk_forward_engine: Optional[IWalkForwardFramework] = None,
        feature_engine: Optional[IFeatureImportanceEngine] = None,
        sweep_engine: Optional[IParameterSweepEngine] = None,
        report_generator: Optional[IReportGenerator] = None,
        repository: Optional[IExperimentRepository] = None,
        event_bus: Optional[IEventBus] = None,
        container: Optional[IContainer] = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._dataset_manager = dataset_manager or self._dataset_manager
        self._strategy_registry = strategy_registry or self._strategy_registry
        self._metrics_engine = metrics_engine or self._metrics_engine
        self._walk_forward_engine = walk_forward_engine or self._walk_forward_engine
        self._feature_engine = feature_engine or self._feature_engine
        self._sweep_engine = sweep_engine or self._sweep_engine
        self._report_generator = report_generator or self._report_generator
        self._repository = repository or self._repository
        self._event_bus = event_bus
        self._container = container
        self._dashboard_backend = ResearchDashboardBackend(self._repository)

    def create_experiment(
        self,
        name: str,
        dataset_version: DatasetVersion,
        strategy_version: StrategyVersion,
        parameters: Optional[Dict[str, Any]] = None,
        seed: int = 42,
    ) -> ExperimentConfig:
        """Create and register a new experiment configuration."""
        self._dataset_manager.register_dataset(dataset_version)
        self._strategy_registry.register_strategy(strategy_version)

        config = ExperimentConfig(
            name=name,
            dataset_version=dataset_version,
            strategy_version=strategy_version,
            parameters=parameters or {},
            seed=seed,
            created_at=datetime.now(timezone.utc),
        )

        if self._event_bus is not None:
            self._event_bus.publish(
                ExperimentCreated(
                    source="research.orchestrator",
                    payload={"experiment_id": config.experiment_id, "name": config.name},
                )
            )

        return config

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute an experiment evaluation pipeline end-to-end with fail-closed error handling and audit manifest generation."""
        start_time = time.time()

        if self._event_bus is not None:
            self._event_bus.publish(
                ExperimentStarted(
                    source="research.orchestrator",
                    payload={"experiment_id": config.experiment_id, "name": config.name},
                )
            )

        try:
            # 1. Retrieve returns inputs from experiment parameters or input dataset
            returns: List[float] = config.parameters.get("returns", [])
            equity_curve: List[float] = config.parameters.get("equity_curve", [])

            if not returns and not equity_curve:
                raise OrchestratorError("No input returns series or evaluation metrics provided. Research Platform consumes results, never simulates them.")

            # 2. Metrics Engine calculation (pure quantitative analysis)
            metrics = self._metrics_engine.calculate_metrics(returns, equity_curve)

            # 3. Walk-Forward Framework evaluation if requested
            walk_forward_res: Optional[WalkForwardResult] = None
            if config.parameters.get("run_walk_forward", True):
                eval_fn = lambda ds, params: self._metrics_engine.calculate_metrics(
                    params.get("returns", returns)
                )
                walk_forward_res = self._walk_forward_engine.evaluate(
                    eval_fn, config.dataset_version, config.parameters
                )
                if self._event_bus is not None:
                    self._event_bus.publish(
                        WalkForwardCompleted(
                            source="research.orchestrator",
                            payload={"experiment_id": config.experiment_id, "windows": len(walk_forward_res.windows)},
                        )
                    )

            # 4. Feature Importance calculation if feature matrix is present
            feature_res: Optional[FeatureImportanceResult] = None
            sample_features = config.parameters.get("sample_features")
            if sample_features and isinstance(sample_features, list):
                feature_res = self._feature_engine.calculate_importance(
                    config.experiment_id, sample_features, returns
                )

            # 5. Parameter Sweep calculation if requested
            sweep_res: Optional[ParameterSweepResult] = None
            sweep_ranges = config.parameters.get("sweep_ranges")
            if sweep_ranges and isinstance(sweep_ranges, dict):
                sweep_id = config.parameters.get("sweep_id") or ParameterSweepConfig.generate_sweep_id(
                    parameter_ranges=sweep_ranges,
                    seed=config.seed,
                    strategy_version=config.strategy_version.version,
                    dataset_version=config.dataset_version.version,
                )
                sweep_cfg = ParameterSweepConfig(
                    sweep_id=sweep_id,
                    parameter_ranges=sweep_ranges,
                    max_iterations=config.parameters.get("max_iterations", 10),
                    seed=config.seed,
                )
                sweep_eval = lambda params: self._metrics_engine.calculate_metrics(
                    params.get("returns", returns)
                )
                sweep_res = self._sweep_engine.run_sweep(sweep_eval, sweep_cfg)
                if self._event_bus is not None:
                    self._event_bus.publish(
                        ParameterSweepCompleted(
                            source="research.orchestrator",
                            payload={"experiment_id": config.experiment_id, "sweep_id": sweep_res.sweep_id},
                        )
                    )

            end_time = time.time()
            execution_time = end_time - start_time

            # 6. Build immutable ResearchManifest
            manifest = self._build_manifest(config, ExperimentStatus.COMPLETED, start_time, end_time)

            result = ExperimentResult(
                experiment_id=config.experiment_id,
                config=config,
                status=ExperimentStatus.COMPLETED,
                metrics=metrics,
                walk_forward=walk_forward_res,
                feature_importance=feature_res,
                parameter_sweep=sweep_res,
                manifest=manifest,
                execution_time_seconds=round(execution_time, 4),
                completed_at=datetime.now(timezone.utc),
            )

            # Persist and update state
            self._state_store.save_experiment(result)
            self._repository.save_experiment(result)

            # Generate default Markdown report
            report = self._report_generator.generate_report(result, ReportFormat.MARKDOWN)

            # Dispatch completion events
            if self._event_bus is not None:
                self._event_bus.publish(
                    ExperimentCompleted(
                        source="research.orchestrator",
                        payload={"experiment_id": result.experiment_id, "status": result.status.value},
                    )
                )
                self._event_bus.publish(
                    ReportGenerated(
                        source="research.orchestrator",
                        payload={"experiment_id": result.experiment_id, "report_id": report.report_id},
                    )
                )

            return result

        except Exception as e:
            logger.error("ResearchOrchestrator: Experiment %s failed execution: %s. Failing closed.", config.experiment_id, e, exc_info=True)

            end_time = time.time()
            execution_time = end_time - start_time

            manifest = self._build_manifest(config, ExperimentStatus.FAILED, start_time, end_time)

            failed_result = ExperimentResult(
                experiment_id=config.experiment_id,
                config=config,
                status=ExperimentStatus.FAILED,
                metrics=PerformanceMetrics(),
                manifest=manifest,
                execution_time_seconds=round(execution_time, 4),
                error_message=str(e),
                completed_at=datetime.now(timezone.utc),
            )

            self._state_store.save_experiment(failed_result)
            self._repository.save_experiment(failed_result)

            if self._event_bus is not None:
                self._event_bus.publish(
                    ExperimentFailed(
                        source="research.orchestrator",
                        payload={"experiment_id": config.experiment_id, "error": str(e)},
                    )
                )

            return failed_result

    def _build_manifest(
        self, config: ExperimentConfig, status: ExperimentStatus, start_time: float, end_time: float
    ) -> ResearchManifest:
        """Build immutable single source of truth ResearchManifest."""
        started_dt = datetime.fromtimestamp(start_time, tz=timezone.utc)
        completed_dt = datetime.fromtimestamp(end_time, tz=timezone.utc)
        duration = max(0.0, end_time - start_time)

        # Resolve Git commit hash safely (Issue 3 resolution)
        git_commit_hash = os.getenv("GIT_COMMIT_SHA")
        if not git_commit_hash:
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    git_commit_hash = res.stdout.strip()
            except Exception:
                pass
        git_commit_hash = git_commit_hash or "UNKNOWN"

        # Compute SHA-256 configuration hash
        config_dict = {
            "experiment_id": config.experiment_id,
            "name": config.name,
            "parameters": str(sorted(config.parameters.items())),
            "seed": config.seed,
        }
        raw_cfg = json.dumps(config_dict, sort_keys=True)
        cfg_hash = hashlib.sha256(raw_cfg.encode("utf-8")).hexdigest()

        manifest_data: Dict[str, Any] = {
            "experiment_id": config.experiment_id,
            "experiment_name": config.name,
            "git_commit_hash": git_commit_hash,
            "toji_version": "1.0.0",
            "dataset_version": config.dataset_version.version,
            "dataset_checksum": config.dataset_version.checksum,
            "strategy_version": config.strategy_version.version,
            "strategy_checksum": config.strategy_version.checksum or "sha256-strat-v1",
            "configuration_hash": cfg_hash,
            "random_seed": config.seed,
            "environment": "production",
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "timezone": "UTC",
            "started_timestamp": started_dt,
            "completed_timestamp": completed_dt,
            "duration_seconds": round(duration, 4),
            "experiment_status": status,
            "report_version": "1.0.0",
        }

        manifest_checksum = ResearchManifest.compute_checksum(manifest_data)
        manifest_data["manifest_checksum"] = manifest_checksum

        return ResearchManifest(**manifest_data)

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Fetch an experiment result by ID."""
        return self._repository.load_experiment(experiment_id)

    def build_dashboard_view(self, experiment_ids: Optional[List[str]] = None) -> ResearchDashboardView:
        """Build visualization state snapshot for research dashboard."""
        return self._dashboard_backend.build_dashboard_view(experiment_ids)

    def generate_report(self, experiment_id: str, format: ReportFormat = ReportFormat.MARKDOWN) -> Optional[ResearchReport]:
        """Generate a research report document for a completed experiment."""
        exp = self.get_experiment(experiment_id)
        if not exp:
            return None
        return self._report_generator.generate_report(exp, format)

    @property
    def dataset_manager(self) -> IDatasetManager:
        return self._dataset_manager

    @property
    def strategy_registry(self) -> IStrategyRegistry:
        return self._strategy_registry

    @property
    def repository(self) -> IExperimentRepository:
        return self._repository
