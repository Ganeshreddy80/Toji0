"""Immutable models for the Feature Platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FeatureRecord(BaseModel):
    """Immutable definition of a feature registered in the platform."""

    uuid: str = Field(..., description="Unique feature UUID.")
    name: str = Field(..., description="Unique technical feature name.")
    display_name: str = Field(..., description="Friendly label.")
    description: str = Field(..., description="Detailed feature description.")
    formula: str = Field(..., description="Mathematical representation string.")
    category: str = Field(..., description="High-level category (e.g. Trend, Momentum, Risk).")
    subcategory: str = Field(..., description="Specific subcategory.")
    owner: str = Field(..., description="Owner team / lead.")
    author: str = Field(..., description="Original creator name.")
    version: str = Field(..., description="Semantic version (e.g. 1.0.0).")
    status: str = Field("DRAFT", description="Lifecycle status (e.g. DRAFT, PROMOTED, RETIRED).")
    tags: List[str] = Field(default_factory=list, description="Custom labels.")
    dependencies: List[str] = Field(default_factory=list, description="Features this feature depends on.")
    input_columns: List[str] = Field(default_factory=list, description="Raw input columns needed (e.g. close).")
    output_columns: List[str] = Field(default_factory=list, description="Output feature columns generated.")
    update_frequency: str = Field(..., description="Trigger frequency (e.g. 1m, 1h, tick).")
    warmup_length: int = Field(..., description="Required historical rows needed before first calculation.")
    lookback_window: int = Field(..., description="Indicator lookback period.")
    required_resolution: str = Field(..., description="Dataset resolution target (e.g. 1m).")
    feature_half_life: float = Field(0.0, description="Memory decay half-life in periods.")
    freshness_policy: int = Field(60, description="Freshness window check in seconds.")
    runtime_cost: float = Field(0.0, description="Estimated CPU calculation cost score.")
    memory_cost: float = Field(0.0, description="Estimated memory score.")
    latency_estimate_ms: float = Field(0.0, description="Average runtime latency in ms.")
    validation_status: str = Field("PENDING", description="Validation outcome (PENDING, APPROVED, REJECTED).")
    created_time: datetime = Field(default_factory=datetime.utcnow)
    updated_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class FeatureMetadata(BaseModel):
    """Metadata store properties containing git, references, hashes."""

    feature_name: str
    formula: str
    description: str
    lookback: int
    lookahead: bool = Field(default=False, description="Whether lookahead bias detected.")
    update_frequency: str
    half_life: float
    confidence_score: float = Field(default=1.0)
    validation_score: float = Field(default=0.0)
    owner: str
    version: str
    source_code_hash: str
    git_commit: str
    experiment_origin: str
    dataset_origin: str
    research_paper: str = Field(default="")

    model_config = ConfigDict(frozen=True)


class FeatureValidationResult(BaseModel):
    """Immutable result of a validation check run against a feature."""

    validation_id: str
    feature_name: str
    nan_ratio: float
    missing_ratio: float
    infinite_values_count: int
    has_lookahead_bias: bool
    data_leakage_detected: bool
    multicollinearity_score: float
    is_stationary: bool
    drift_score: float
    latency_ms: float
    memory_usage_mb: float
    pit_correctness_passed: bool
    is_approved: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class LineageNode(BaseModel):
    """Trace node for calculating full feature lineage paths."""

    node_id: str
    name: str
    type: str  # e.g. raw_column, feature, strategy, backtest, live
    parents: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class FeatureVersionInfo(BaseModel):
    """Immutable model representing semantic version audits."""

    uuid: str
    feature_name: str
    semantic_version: str
    sha256_hash: str
    git_commit: str
    author: str
    experiment_id: str
    validation_version: str
    dataset_version: str
    formula_version: str
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    last_validation_time: Optional[datetime] = None
    promotion_status: str = Field("DRAFT")

    model_config = ConfigDict(frozen=True)


class FeatureFreshnessMetrics(BaseModel):
    """Immutable model for exponential decay and tracking freshness age checks."""

    feature_name: str
    half_life_seconds: float
    freshness_score: float
    age_seconds: float
    decay_rate: float
    recalculation_frequency: str
    expiration_policy: int
    last_successful_refresh: datetime
    expected_refresh: datetime

    model_config = ConfigDict(frozen=True)


class FeatureQualityScore(BaseModel):
    """Immutable model summarizing multi-dimensional validation metrics."""

    feature_name: str
    overall_score: float
    completeness: float
    stability: float
    missing_ratio: float
    drift_score: float
    stationarity: bool
    variance_stability: float
    correlation_health: float
    memory_cost: float
    cpu_cost: float
    latency_ms: float
    reproducibility_score: float
    pit_correctness: bool

    model_config = ConfigDict(frozen=True)


class FeatureImportanceMetrics(BaseModel):
    """Immutable model mapping predictive scores against a return vector."""

    feature_name: str
    target_name: str
    mutual_information: float
    information_coefficient: float
    information_ratio: float
    permutation_importance: float
    feature_rank: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class OrthogonalizationReport(BaseModel):
    """Collinearity report identifying data overlap and groups."""

    feature_name: str
    collinear_features: Dict[str, float] = Field(default_factory=dict)
    redundant_features: List[str] = Field(default_factory=list)
    maximum_correlation: float
    overlap_group: str
    recommended_action: str

    model_config = ConfigDict(frozen=True)


class FeatureMathematicalMetadata(BaseModel):
    """Mathematical properties, references, regimes, and asset boundaries."""

    feature_name: str
    formula: str
    scientific_reference: str
    research_paper: str
    expected_distribution: str
    assumptions: List[str] = Field(default_factory=list)
    failure_modes: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    market_regimes: List[str] = Field(default_factory=list)
    asset_classes: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    output_type: str

    model_config = ConfigDict(frozen=True)


class FeatureApprovalReport(BaseModel):
    """Promotion governance signed audit report."""

    report_id: str
    feature_name: str
    version: str
    validation_status: str
    drift_check_passed: bool
    freshness_check_passed: bool
    pit_validation_passed: bool
    dependency_validation_passed: bool
    version_validation_passed: bool
    metadata_validation_passed: bool
    lineage_validation_passed: bool
    approved_by: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
