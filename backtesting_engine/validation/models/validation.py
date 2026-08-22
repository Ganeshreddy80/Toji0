"""Immutable Pydantic V2 models for Walk-Forward Validation Engine (Sprint 8B)."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backtesting_engine.analytics.models.analytics import AnalyticsContext, AnalyticsReport


class ValidationMethod(enum.Enum):
    """Supported chronological walk-forward window generation methods."""

    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"
    ANCHORED = "ANCHORED"


class WalkForwardConfig(BaseModel):
    """Authoritative immutable configuration for walk-forward validation execution."""

    training_window: int = Field(..., gt=0, description="Size of training window in historical bars.")
    testing_window: int = Field(..., gt=0, description="Size of testing window in historical bars.")
    step_size: int = Field(..., gt=0, description="Step size to advance windows in historical bars.")
    validation_method: ValidationMethod = Field(default=ValidationMethod.ROLLING, description="Walk-forward window generation method.")
    minimum_trades: int = Field(default=1, ge=0, description="Minimum trades per fold required.")
    minimum_history: int = Field(default=10, gt=0, description="Minimum total historical bars required.")
    random_seed: int = Field(default=42, description="Random seed for deterministic replay.")
    overfitting_threshold: float = Field(default=50.0, ge=0.0, le=100.0, description="Max allowed overfitting score threshold [0, 100].")
    stability_threshold: float = Field(default=50.0, ge=0.0, le=100.0, description="Min required stability score threshold [0, 100].")
    context: AnalyticsContext = Field(default_factory=AnalyticsContext, description="Portfolio analytics configuration context.")

    model_config = ConfigDict(frozen=True)


class ValidationWindow(BaseModel):
    """Immutable representation of a single chronological training/testing fold window."""

    fold_number: int = Field(..., ge=1, description="Sequential fold number (1-indexed).")
    train_start: datetime = Field(..., description="Train window start timestamp.")
    train_end: datetime = Field(..., description="Train window end timestamp.")
    test_start: datetime = Field(..., description="Test window start timestamp.")
    test_end: datetime = Field(..., description="Test window end timestamp.")
    train_start_idx: int = Field(..., ge=0, description="Train start bar index.")
    train_end_idx: int = Field(..., ge=0, description="Train end bar index (inclusive).")
    test_start_idx: int = Field(..., ge=0, description="Test start bar index.")
    test_end_idx: int = Field(..., ge=0, description="Test end bar index (inclusive).")

    model_config = ConfigDict(frozen=True)


class FoldResult(BaseModel):
    """Immutable result of a single walk-forward fold execution."""

    fold_number: int = Field(..., ge=1, description="Fold number.")
    window: ValidationWindow = Field(..., description="Validation window specifications.")
    train_metrics: AnalyticsReport = Field(..., description="Analytics report for training period.")
    test_metrics: AnalyticsReport = Field(..., description="Analytics report for testing period.")
    train_trades: int = Field(default=0, ge=0, description="Number of training trades.")
    test_trades: int = Field(default=0, ge=0, description="Number of testing trades.")
    performance_drift: float = Field(default=0.0, description="Relative return drift between test and train.")
    sharpe_drift: float = Field(default=0.0, description="Sharpe ratio drift (Test Sharpe - Train Sharpe).")
    drawdown_drift: float = Field(default=0.0, description="Drawdown drift (Test MaxDD - Train MaxDD).")
    trade_count_drift: float = Field(default=0.0, description="Trade count ratio (Test Trades / Train Trades).")
    execution_time_seconds: float = Field(default=0.0, ge=0.0, description="Execution duration for fold in seconds.")
    warnings: List[str] = Field(default_factory=list, description="Execution or validation warnings.")

    model_config = ConfigDict(frozen=True)


class WalkForwardReport(BaseModel):
    """Immutable authoritative output report of walk-forward validation run."""

    folds: List[FoldResult] = Field(..., description="List of individual fold execution results.")
    average_train_return: float = Field(default=0.0, description="Mean total return across training folds.")
    average_test_return: float = Field(default=0.0, description="Mean total return across testing folds.")
    average_drawdown: float = Field(default=0.0, ge=0.0, le=1.0, description="Mean max drawdown across testing folds.")
    average_sharpe: float = Field(default=0.0, description="Mean Sharpe ratio across testing folds.")
    stability_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall performance & risk persistence score [0, 100].")
    degradation_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Mean degradation ratio across testing folds [0, 1].")
    overfitting_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Deterministic overfitting score [0, 100].")
    consistency_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Fold-to-fold consistency score [0, 100].")
    passed: bool = Field(..., description="True if walk-forward validation passed stability and overfitting thresholds.")
    config: WalkForwardConfig = Field(..., description="Configuration used for validation run.")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timezone-aware UTC report generation timestamp.")
    engine_version: str = Field(default="1.0.0", description="Walk-forward engine version.")

    @field_validator("generated_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Enforce timezone-aware UTC datetime for report generation."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("WalkForwardReport generated_at must be timezone-aware (e.g. UTC).")
        return v

    model_config = ConfigDict(frozen=True)
