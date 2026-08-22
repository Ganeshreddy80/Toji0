"""Immutable Pydantic models for the Validation Core.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ValidationConfiguration(BaseModel):
    """Validation process settings and checks."""

    backtest_id: str
    cv_method: str = Field("CPCV", description="Blocked, Purged, CPCV, etc.")
    pbo_enabled: bool = True
    psr_enabled: bool = True
    dsr_enabled: bool = True
    regime_enabled: bool = True
    drift_enabled: bool = True
    weights: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class StatisticalMetrics(BaseModel):
    """Statistical verification outputs."""

    sharpe: float
    psr: float
    dsr: float
    pbo: float
    spa_p_value: float
    reality_check_p_value: float
    robust_t_stat: float

    model_config = ConfigDict(frozen=True)


class ValidationDecision(BaseModel):
    """Specific governance validation checkpoint gate status."""

    check_name: str
    status: str  # e.g. PASSED, FAILED
    detail: str

    model_config = ConfigDict(frozen=True)


class ValidationSummary(BaseModel):
    """Summary of cross-validation iterations metrics."""

    total_runs: int
    pass_ratio: float
    avg_sharpe: float
    max_drawdown: float

    model_config = ConfigDict(frozen=True)


class CrossValidationResult(BaseModel):
    """Output metrics for a single cross-validation split."""

    split_index: int
    train_sharpe: float
    test_sharpe: float
    train_samples: int
    test_samples: int

    model_config = ConfigDict(frozen=True)


class BootstrapResult(BaseModel):
    """Bootstrap statistical indicators."""

    original_stat: float
    mean_stat: float
    std_stat: float
    p_value: float
    lower_ci: float
    upper_ci: float

    model_config = ConfigDict(frozen=True)


class RegimeValidationResult(BaseModel):
    """Performance metrics broken down by market regime."""

    regime_name: str
    sharpe: float
    total_samples: int
    max_drawdown: float

    model_config = ConfigDict(frozen=True)


class DriftValidationResult(BaseModel):
    """Feature or concept drift metrics."""

    feature_name: str
    psi: float
    kl_divergence: float
    js_divergence: float
    severity: str  # NONE, LOW, HIGH

    model_config = ConfigDict(frozen=True)


class ResearchScore(BaseModel):
    """Aggregated quantitative research suitability score (0-100 scale)."""

    score_value: float
    quality_contrib: float
    freshness_contrib: float
    drift_contrib: float
    pbo_contrib: float
    psr_contrib: float
    dsr_contrib: float
    spa_contrib: float
    regime_stability_contrib: float

    model_config = ConfigDict(frozen=True)


class ValidationReport(BaseModel):
    """The signed, immutable final validation report containing all checks outcomes."""

    report_id: str
    backtest_id: str
    summary: ValidationSummary
    decisions: List[ValidationDecision]
    metrics: StatisticalMetrics
    cv_results: List[CrossValidationResult] = Field(default_factory=list)
    regime_results: List[RegimeValidationResult] = Field(default_factory=list)
    drift_results: List[DriftValidationResult] = Field(default_factory=list)
    research_score: ResearchScore
    is_approved: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ValidationRun(BaseModel):
    """Wrapper tracking execution status and results."""

    run_id: str
    configuration: ValidationConfiguration
    status: str = Field("PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    report: Optional[ValidationReport] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
