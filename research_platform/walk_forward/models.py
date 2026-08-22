"""Immutable Pydantic models for Walk Forward Validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Any
from pydantic import BaseModel, ConfigDict, Field


class ValidationWindow(BaseModel):
    """An optimization window containing training and testing boundaries."""

    window_id: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    in_sample_sharpe: float
    out_of_sample_sharpe: float

    model_config = ConfigDict(frozen=True)


class SensitivityScore(BaseModel):
    """Parameter sensitivity analysis logs."""

    parameter_name: str
    values: List[float] = Field(default_factory=list)
    metrics_deviation: float
    score: float  # High score indicates high robustness

    model_config = ConfigDict(frozen=True)


class OverfittingCard(BaseModel):
    """Overfitting diagnostics summary card."""

    strategy_id: str
    is_overfitted: bool
    probability_of_backtest_overfitting: float
    stability_score: float

    model_config = ConfigDict(frozen=True)
