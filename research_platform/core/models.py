"""Immutable Pydantic V2 models for the Research Platform (Sprint 6)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from research_platform.core.enums import (
    DatasetType,
    ExperimentStatus,
    MetricType,
    ReportFormat,
    StrategyType,
    SweepMethod,
    WalkForwardType,
)


class DatasetVersion(BaseModel):
    """Immutable metadata and version specification for a research dataset."""

    dataset_id: str = Field(..., description="Unique dataset identifier.")
    name: str = Field(..., description="Human-readable dataset name.")
    version: str = Field(..., description="Version string (e.g. 'v1.0.0').")
    dataset_type: DatasetType = Field(default=DatasetType.OHLCV, description="Dataset classification.")
    checksum: str = Field(..., description="SHA-256 hash or data integrity checksum.")
    start_time: datetime = Field(..., description="Data start boundary timestamp.")
    end_time: datetime = Field(..., description="Data end boundary timestamp.")
    record_count: int = Field(..., ge=0, description="Total record/candle count.")
    symbols: List[str] = Field(default_factory=list, description="Symbols contained in dataset.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional dataset attributes.")

    model_config = ConfigDict(frozen=True)


class StrategyVersion(BaseModel):
    """Immutable metadata and parameters for a research strategy version."""

    strategy_id: str = Field(..., description="Unique strategy identifier.")
    name: str = Field(..., description="Strategy name.")
    version: str = Field(..., description="Strategy code/config version string.")
    strategy_type: StrategyType = Field(default=StrategyType.QUANTITATIVE, description="Strategy domain classification.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy input parameters.")
    author: str = Field(default="system", description="Author or system creator.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp.")
    checksum: str = Field(default="", description="Source or configuration checksum.")

    model_config = ConfigDict(frozen=True)


class ResearchMetric(BaseModel):
    """Immutable single performance or risk metric."""

    metric_type: MetricType = Field(..., description="Metric classification type.")
    value: float = Field(..., description="Calculated metric value.")
    category: str = Field(default="PERFORMANCE", description="Category (PERFORMANCE, RISK, TAIL).")
    description: str = Field(default="", description="Detailed description.")

    model_config = ConfigDict(frozen=True)


class PerformanceMetrics(BaseModel):
    """Immutable unified performance and risk metrics evaluated by Research Platform."""

    sharpe_ratio: float = Field(default=0.0, description="Annualized Sharpe ratio.")
    sortino_ratio: float = Field(default=0.0, description="Annualized Sortino ratio.")
    max_drawdown: float = Field(default=0.0, ge=0.0, le=1.0, description="Maximum peak-to-trough drawdown ratio [0.0, 1.0].")
    calmar_ratio: float = Field(default=0.0, description="Calmar ratio (CAGR / Max Drawdown).")
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Winning trade ratio [0.0, 1.0].")
    profit_factor: float = Field(default=0.0, ge=0.0, description="Gross profit / Gross loss ratio.")
    cagr: float = Field(default=0.0, description="Compound Annual Growth Rate.")
    annualized_volatility: float = Field(default=0.0, ge=0.0, description="Annualized volatility.")
    expected_return: float = Field(default=0.0, description="Expected return per trade/period.")
    value_at_risk_95: float = Field(default=0.0, description="95% Value at Risk (VaR).")
    tail_risk: float = Field(default=0.0, description="Tail risk / Conditional VaR (CVaR 95%).")
    total_trades: int = Field(default=0, ge=0, description="Total trade count.")
    winning_trades: int = Field(default=0, ge=0, description="Winning trade count.")
    losing_trades: int = Field(default=0, ge=0, description="Losing trade count.")

    model_config = ConfigDict(frozen=True)


class FeatureImportance(BaseModel):
    """Immutable single feature attribution score."""

    feature_name: str = Field(..., description="Name of feature.")
    importance_score: float = Field(..., description="Attribution score.")
    rank: int = Field(..., ge=1, description="Importance rank position.")
    method: str = Field(default="PERMUTATION", description="Evaluation method (PERMUTATION, CORRELATION).")
    p_value: Optional[float] = Field(default=None, description="Statistical significance p-value.")

    model_config = ConfigDict(frozen=True)


class FeatureImportanceResult(BaseModel):
    """Immutable aggregated feature importance evaluation result."""

    experiment_id: str = Field(..., description="Associated experiment ID.")
    method: str = Field(..., description="Evaluation method.")
    features: List[FeatureImportance] = Field(default_factory=list, description="Feature importance rankings.")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation timestamp.")

    model_config = ConfigDict(frozen=True)


class ParameterSweepConfig(BaseModel):
    """Immutable parameter sweep configuration."""

    sweep_id: str = Field(default="", description="Sweep ID. Generated deterministically if omitted.")
    method: SweepMethod = Field(default=SweepMethod.GRID, description="Sweep search algorithm.")
    parameter_ranges: Dict[str, List[Any]] = Field(..., description="Parameter names mapped to candidate values.")
    max_iterations: int = Field(default=100, ge=1, description="Max iteration limit.")
    seed: int = Field(default=42, description="Random seed for reproducible sweeps.")

    model_config = ConfigDict(frozen=True)

    @classmethod
    def generate_sweep_id(
        cls,
        parameter_ranges: Dict[str, List[Any]],
        seed: int = 42,
        strategy_version: str = "",
        dataset_version: str = "",
    ) -> str:
        """Generate a deterministic SHA-256 sweep_id from parameter ranges, seed, strategy version, and dataset version."""
        sorted_ranges = {k: str(v) for k, v in sorted(parameter_ranges.items())}
        raw_str = f"{sorted_ranges}|{seed}|{strategy_version}|{dataset_version}"
        return f"sweep-{hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:16]}"


class ParameterSweepTrial(BaseModel):
    """Immutable single parameter sweep trial result."""

    trial_id: str = Field(..., description="Trial unique ID.")
    parameters: Dict[str, Any] = Field(..., description="Evaluated trial parameters.")
    metrics: PerformanceMetrics = Field(..., description="Performance metrics resulting from trial.")
    rank: int = Field(default=1, ge=1, description="Rank position among sweep trials.")

    model_config = ConfigDict(frozen=True)


class ParameterSweepResult(BaseModel):
    """Immutable parameter sweep evaluation result."""

    sweep_id: str = Field(..., description="Associated sweep ID.")
    best_parameters: Dict[str, Any] = Field(..., description="Optimal parameter configuration.")
    best_metrics: PerformanceMetrics = Field(..., description="Metrics of best trial.")
    trials: List[ParameterSweepTrial] = Field(default_factory=list, description="All sweep trial results.")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Completion timestamp.")

    model_config = ConfigDict(frozen=True)


class WalkForwardWindow(BaseModel):
    """Immutable walk-forward window partition and evaluation metrics."""

    window_index: int = Field(..., ge=0, description="Sequential window index.")
    in_sample_start: datetime = Field(..., description="In-sample start boundary.")
    in_sample_end: datetime = Field(..., description="In-sample end boundary.")
    out_of_sample_start: datetime = Field(..., description="Out-of-sample start boundary.")
    out_of_sample_end: datetime = Field(..., description="Out-of-sample end boundary.")
    in_sample_metrics: PerformanceMetrics = Field(..., description="In-sample metrics.")
    out_of_sample_metrics: PerformanceMetrics = Field(..., description="Out-of-sample metrics.")
    efficiency_ratio: float = Field(default=1.0, description="Out-of-sample vs In-sample Sharpe ratio.")

    model_config = ConfigDict(frozen=True)


class WalkForwardResult(BaseModel):
    """Immutable walk-forward framework evaluation result."""

    framework_type: WalkForwardType = Field(default=WalkForwardType.ROLLING, description="Window partitioning type.")
    windows: List[WalkForwardWindow] = Field(default_factory=list, description="Partitioned window evaluations.")
    average_efficiency: float = Field(default=1.0, description="Average efficiency ratio across windows.")
    overall_out_of_sample_metrics: PerformanceMetrics = Field(..., description="Combined out-of-sample metrics.")
    stability_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Performance stability score [0.0, 1.0].")

    model_config = ConfigDict(frozen=True)


class ResearchManifest(BaseModel):
    """Immutable single source of truth audit manifest for research experiments."""

    experiment_id: str = Field(..., description="Experiment UUID.")
    experiment_name: str = Field(..., description="Experiment name.")
    git_commit_hash: str = Field(..., description="Git commit hash.")
    toji_version: str = Field(default="1.0.0", description="TOJI platform version.")
    dataset_version: str = Field(..., description="Dataset version string.")
    dataset_checksum: str = Field(..., description="SHA-256 dataset checksum.")
    strategy_version: str = Field(..., description="Strategy version string.")
    strategy_checksum: str = Field(..., description="SHA-256 strategy checksum.")
    configuration_hash: str = Field(..., description="SHA-256 experiment configuration hash.")
    random_seed: int = Field(..., description="PRNG seed for deterministic evaluation.")
    environment: str = Field(default="production", description="Execution environment.")
    python_version: str = Field(..., description="Python runtime version.")
    platform: str = Field(..., description="Operating system platform.")
    timezone: str = Field(default="UTC", description="System execution timezone.")
    started_timestamp: datetime = Field(..., description="Experiment execution start timestamp.")
    completed_timestamp: datetime = Field(..., description="Experiment execution completion timestamp.")
    duration_seconds: float = Field(..., ge=0.0, description="Execution duration in seconds.")
    experiment_status: ExperimentStatus = Field(..., description="Final experiment status.")
    report_version: str = Field(default="1.0.0", description="Report generator version.")
    manifest_checksum: str = Field(..., description="SHA-256 integrity checksum over all manifest fields.")

    model_config = ConfigDict(frozen=True)

    @classmethod
    def compute_checksum(cls, data_dict: Dict[str, Any]) -> str:
        """Compute deterministic SHA-256 checksum over manifest key-values excluding wall-clock timestamps and duration."""
        ignore_keys = {"manifest_checksum", "started_timestamp", "completed_timestamp", "duration_seconds"}
        filtered = {k: str(v) for k, v in sorted(data_dict.items()) if k not in ignore_keys}
        raw_str = "|".join(f"{k}:{filtered[k]}" for k in sorted(filtered.keys()))
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


class ExperimentConfig(BaseModel):
    """Immutable experiment specification."""

    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Experiment ID.")
    name: str = Field(..., description="Experiment title.")
    description: str = Field(default="", description="Experiment purpose.")
    dataset_version: DatasetVersion = Field(..., description="Associated immutable dataset version.")
    strategy_version: StrategyVersion = Field(..., description="Associated immutable strategy version.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Experiment runtime parameter overrides.")
    seed: int = Field(default=42, description="Random seed for reproducibility.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp.")

    model_config = ConfigDict(frozen=True)


class ExperimentResult(BaseModel):
    """Immutable full output result of a research experiment execution."""

    experiment_id: str = Field(..., description="Experiment UUID.")
    config: ExperimentConfig = Field(..., description="Experiment configuration.")
    status: ExperimentStatus = Field(..., description="Final experiment status.")
    metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics, description="Evaluated metrics.")
    walk_forward: Optional[WalkForwardResult] = Field(default=None, description="Walk-forward analysis result.")
    feature_importance: Optional[FeatureImportanceResult] = Field(default=None, description="Feature importance result.")
    parameter_sweep: Optional[ParameterSweepResult] = Field(default=None, description="Parameter sweep result.")
    manifest: Optional[ResearchManifest] = Field(default=None, description="Immutable audit manifest single source of truth.")
    execution_time_seconds: float = Field(default=0.0, ge=0.0, description="Execution duration in seconds.")
    error_message: Optional[str] = Field(default=None, description="Failure error details if failed.")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Completion timestamp.")

    model_config = ConfigDict(frozen=True)


class ResearchReport(BaseModel):
    """Immutable research report document model."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Report UUID.")
    experiment_id: str = Field(..., description="Associated experiment ID.")
    title: str = Field(..., description="Report document title.")
    format: ReportFormat = Field(default=ReportFormat.MARKDOWN, description="Report document format.")
    summary: str = Field(..., description="Executive summary.")
    content: str = Field(..., description="Full formatted report body.")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Generation timestamp.")

    model_config = ConfigDict(frozen=True)


class ResearchDashboardView(BaseModel):
    """Immutable research dashboard backend visualization state."""

    experiment_count: int = Field(default=0, ge=0, description="Total experiments stored.")
    top_experiments: List[ExperimentResult] = Field(default_factory=list, description="Top performing experiments.")
    metric_summaries: Dict[str, float] = Field(default_factory=dict, description="Summary metric averages across research platform.")
    heatmap_data: Dict[str, Any] = Field(default_factory=dict, description="Parameter sweep heatmap dataset.")
    equity_curves: Dict[str, List[float]] = Field(default_factory=dict, description="Equity curve series mapped by experiment ID.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp.")

    model_config = ConfigDict(frozen=True)
