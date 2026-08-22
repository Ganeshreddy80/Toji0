"""Immutable Pydantic models for the Meta Portfolio Optimizer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AllocationRequest(BaseModel):
    """Constraints and inputs for a rebalancing optimization run."""

    symbols: List[str]
    current_weights: Dict[str, float] = Field(default_factory=dict)
    cash: float = 100000.0

    model_config = ConfigDict(frozen=True)


class OptimizationParameters(BaseModel):
    """Target risk, return, and position limits."""

    risk_tolerance: float = 0.5
    min_weight: float = 0.0
    max_weight: float = 1.0
    target_return: Optional[float] = None

    model_config = ConfigDict(frozen=True)


class CorrelationMatrix(BaseModel):
    """Asset or strategy correlation structure data."""

    symbols: List[str]
    matrix: List[List[float]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class RiskBudget(BaseModel):
    """Marginal risk contributions and budget limits."""

    limits: Dict[str, float] = Field(default_factory=dict)
    marginal_contributions: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class OptimizerResult(BaseModel):
    """The computed optimal weights, volatility and return metrics."""

    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class PortfolioAllocation(BaseModel):
    """Persisted portfolio allocation state history record."""

    allocation_id: str
    weights: Dict[str, float]
    net_exposure: float
    gross_exposure: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
