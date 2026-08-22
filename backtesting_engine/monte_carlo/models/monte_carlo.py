"""Immutable Pydantic V2 models for the Monte Carlo Simulation Engine (Sprint 8C)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BootstrapMethod(str, Enum):
    """Resampling method for bootstrap simulations."""

    TRADE = "TRADE"
    RETURN = "RETURN"
    BLOCK = "BLOCK"


class MonteCarloConfig(BaseModel):
    """Immutable configuration for Monte Carlo simulation run."""

    iterations: int = Field(default=1000, gt=0, description="Number of simulation paths to run.")
    bootstrap_method: BootstrapMethod = Field(default=BootstrapMethod.TRADE, description="Resampling strategy.")
    random_seed: Optional[int] = Field(default=42, description="Seed for pseudo-random number generator.")
    confidence_levels: List[float] = Field(
        default_factory=lambda: [0.90, 0.95, 0.99],
        description="Target confidence levels for interval estimation.",
    )
    block_size: int = Field(default=5, ge=1, description="Block size for block bootstrap strategy.")
    preserve_trade_order: bool = Field(default=False, description="Whether trade ordering constraint applies.")
    ruin_threshold_pct: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Peak-to-trough drawdown threshold defining account ruin (e.g. 0.50 = 50% loss).",
    )
    deterministic: bool = Field(default=True, description="Whether simulation requires strict deterministic seed.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when configuration was created.",
    )

    @field_validator("confidence_levels")
    @classmethod
    def validate_confidence_levels(cls, v: List[float]) -> List[float]:
        """Ensure confidence levels are within (0.0, 1.0)."""
        if not v:
            raise ValueError("confidence_levels cannot be empty.")
        for cl in v:
            if not (0.0 < cl < 1.0):
                raise ValueError(f"Confidence level {cl} must be strictly between 0 and 1.")
        return sorted(v)

    model_config = ConfigDict(frozen=True)


class SimulationResult(BaseModel):
    """Immutable result of a single Monte Carlo equity path simulation."""

    iteration: int = Field(..., ge=0, description="Simulation run iteration index.")
    ending_equity: float = Field(..., description="Final equity level at simulation end.")
    max_drawdown: float = Field(..., ge=0.0, le=1.0, description="Maximum peak-to-trough drawdown ratio [0.0, 1.0].")
    total_return: float = Field(..., description="Total cumulative return ratio.")
    cagr: float = Field(..., description="Compound annual growth rate.")
    sharpe: float = Field(..., description="Annualized Sharpe ratio.")
    ruin: bool = Field(..., description="True if account hit ruin threshold during simulation.")

    model_config = ConfigDict(frozen=True)


class ConfidenceInterval(BaseModel):
    """Immutable confidence interval estimation for a statistical metric."""

    metric: str = Field(..., description="Name of performance or risk metric.")
    confidence_level: float = Field(..., gt=0.0, lt=1.0, description="Confidence level (e.g. 0.95 for 95%).")
    lower_bound: float = Field(..., description="Lower bound of confidence interval.")
    upper_bound: float = Field(..., description="Upper bound of confidence interval.")

    model_config = ConfigDict(frozen=True)


class MonteCarloReport(BaseModel):
    """Immutable summary report containing all Monte Carlo simulation outputs."""

    simulations: List[SimulationResult] = Field(..., description="Individual simulation path results.")
    confidence_intervals: List[ConfidenceInterval] = Field(..., description="Computed confidence intervals.")
    risk_of_ruin: float = Field(..., ge=0.0, le=1.0, description="Probability of account ruin across all runs.")
    expected_return: float = Field(..., description="Mean total return across simulations.")
    expected_drawdown: float = Field(..., ge=0.0, le=1.0, description="Mean maximum drawdown across simulations.")
    percentile_table: Dict[str, Dict[str, float]] = Field(..., description="Percentile breakdown per metric.")
    summary: Dict[str, Any] = Field(..., description="High-level statistical summary metrics.")

    model_config = ConfigDict(frozen=True)
