"""Abstract interfaces for the Research Platform (Sprint 6)."""

from __future__ import annotations

import abc
from typing import Any, Callable, Dict, List, Optional

from research_platform.core.enums import ReportFormat
from research_platform.core.models import (
    DatasetVersion,
    ExperimentConfig,
    ExperimentResult,
    FeatureImportanceResult,
    ParameterSweepConfig,
    ParameterSweepResult,
    PerformanceMetrics,
    ResearchDashboardView,
    ResearchReport,
    StrategyVersion,
    WalkForwardResult,
)


class IDatasetManager(abc.ABC):
    """Protocol for managing immutable market research datasets."""

    @abc.abstractmethod
    def register_dataset(self, dataset: DatasetVersion) -> None:
        """Register an immutable dataset version."""

    @abc.abstractmethod
    def get_dataset(self, dataset_id: str, version: Optional[str] = None) -> Optional[DatasetVersion]:
        """Fetch a dataset version by ID and version string."""

    @abc.abstractmethod
    def list_datasets(self) -> List[DatasetVersion]:
        """List all registered dataset versions."""


class IStrategyRegistry(abc.ABC):
    """Protocol for managing research strategy versions."""

    @abc.abstractmethod
    def register_strategy(self, strategy: StrategyVersion) -> None:
        """Register a strategy version."""

    @abc.abstractmethod
    def get_strategy(self, strategy_id: str, version: Optional[str] = None) -> Optional[StrategyVersion]:
        """Retrieve a registered strategy version."""

    @abc.abstractmethod
    def list_strategies(self) -> List[StrategyVersion]:
        """List all registered strategies."""


class IMetricsEngine(abc.ABC):
    """Protocol for calculating quantitative performance and risk metrics."""

    @abc.abstractmethod
    def calculate_metrics(
        self, returns: List[float], equity_curve: Optional[List[float]] = None, risk_free_rate: float = 0.0
    ) -> PerformanceMetrics:
        """Calculate deterministic performance metrics from returns or equity curve."""


class IFeatureImportanceEngine(abc.ABC):
    """Protocol for computing feature attribution scores."""

    @abc.abstractmethod
    def calculate_importance(
        self,
        experiment_id: str,
        feature_matrix: List[Dict[str, float]],
        target_returns: List[float],
        method: str = "PERMUTATION",
    ) -> FeatureImportanceResult:
        """Compute feature importance rankings."""


class IParameterSweepEngine(abc.ABC):
    """Protocol for parameter sweep optimization."""

    @abc.abstractmethod
    def run_sweep(
        self,
        eval_fn: Callable[[Dict[str, Any]], PerformanceMetrics],
        config: ParameterSweepConfig,
    ) -> ParameterSweepResult:
        """Execute a parameter sweep search."""


class IWalkForwardFramework(abc.ABC):
    """Protocol for walk-forward out-of-sample evaluation."""

    @abc.abstractmethod
    def evaluate(
        self,
        eval_fn: Callable[[DatasetVersion, Dict[str, Any]], PerformanceMetrics],
        dataset: DatasetVersion,
        parameters: Dict[str, Any],
        train_window_ratio: float = 0.7,
        num_windows: int = 5,
    ) -> WalkForwardResult:
        """Run walk-forward window evaluation."""


class IExperimentRepository(abc.ABC):
    """Protocol for persisting experiment configurations and execution results."""

    @abc.abstractmethod
    def save_experiment(self, result: ExperimentResult) -> None:
        """Persist an experiment result."""

    @abc.abstractmethod
    def load_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Load an experiment result by ID."""

    @abc.abstractmethod
    def list_experiments(self) -> List[ExperimentResult]:
        """Retrieve all historical experiment results."""


class IReportGenerator(abc.ABC):
    """Protocol for generating research reports."""

    @abc.abstractmethod
    def generate_report(
        self, result: ExperimentResult, format: ReportFormat = ReportFormat.MARKDOWN
    ) -> ResearchReport:
        """Generate a structured research report document."""


class IResearchDashboardBackend(abc.ABC):
    """Protocol for building dashboard visualization states."""

    @abc.abstractmethod
    def build_dashboard_view(self, experiment_ids: Optional[List[str]] = None) -> ResearchDashboardView:
        """Build visualization state snapshot for the research dashboard."""


class IExperimentManager(abc.ABC):
    """Authoritative protocol for managing experiment lifecycles."""

    @abc.abstractmethod
    def create_experiment(
        self,
        name: str,
        dataset_version: DatasetVersion,
        strategy_version: StrategyVersion,
        parameters: Optional[Dict[str, Any]] = None,
        seed: int = 42,
    ) -> ExperimentConfig:
        """Create a new experiment configuration."""

    @abc.abstractmethod
    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute an experiment pipeline end-to-end."""

    @abc.abstractmethod
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Fetch an experiment result."""
