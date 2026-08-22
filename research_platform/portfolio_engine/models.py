"""Immutable Pydantic models for the Portfolio Construction & Risk Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortfolioPosition(BaseModel):
    """Specific asset position holding inside a portfolio snapshot."""

    symbol: str
    quantity: float
    weight: float
    avg_price: float
    market_value: float

    model_config = ConfigDict(frozen=True)


class PortfolioSnapshot(BaseModel):
    """Snapshot representing the portfolio state at a specific point in time."""

    timestamp: datetime
    positions: Dict[str, PortfolioPosition] = Field(default_factory=dict)
    cash: float
    total_value: float

    model_config = ConfigDict(frozen=True)


class PortfolioMetadata(BaseModel):
    """Metadata tag indicators for portfolio records."""

    author: str
    notes: str = ""
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioLifecycle(BaseModel):
    """Tracks state progression of a portfolio structure."""

    status: str = "DRAFT"  # DRAFT, ACTIVE, REBALANCING, RETIRED
    effective_time: datetime
    retired_time: Optional[datetime] = None

    model_config = ConfigDict(frozen=True)


class PortfolioVersion(BaseModel):
    """Tracks updates or version configurations."""

    version_num: str
    changelog: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class Portfolio(BaseModel):
    """High-level catalog record mapping portfolios."""

    portfolio_id: str
    name: str
    display_name: str
    description: str
    version: PortfolioVersion
    lifecycle: PortfolioLifecycle
    metadata: PortfolioMetadata

    model_config = ConfigDict(frozen=True)


class PortfolioWeights(BaseModel):
    """Assigned allocation weight vectors."""

    weights: Dict[str, float] = Field(default_factory=dict)
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class AllocationResult(BaseModel):
    """Outputs representing allocation results."""

    allocator_name: str
    weights: PortfolioWeights
    total_allocated: float

    model_config = ConfigDict(frozen=True)


class OptimizationResult(BaseModel):
    """Calculated optimizer allocations."""

    optimizer_name: str
    weights: PortfolioWeights
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float

    model_config = ConfigDict(frozen=True)


class CovarianceMatrix(BaseModel):
    """Estimated covariance matrix mappings."""

    matrix: List[List[float]] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class ForecastResult(BaseModel):
    """Expected return forecasts mapping."""

    forecasts: Dict[str, float] = Field(default_factory=dict)
    forecast_type: str
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class RiskContribution(BaseModel):
    """Calculated component risk metrics."""

    marginal_contribution: Dict[str, float] = Field(default_factory=dict)
    component_contribution: Dict[str, float] = Field(default_factory=dict)
    percentage_contribution: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class RiskBudget(BaseModel):
    """Risk allocation targets."""

    target_contributions: Dict[str, float] = Field(default_factory=dict)
    max_cvar: float = 0.10
    max_var: float = 0.05

    model_config = ConfigDict(frozen=True)


class ConstraintViolation(BaseModel):
    """Constraint violation warnings."""

    constraint_name: str
    violated: bool
    details: str

    model_config = ConfigDict(frozen=True)


class RebalancePlan(BaseModel):
    """Rebalancing trade schedules."""

    plan_id: str
    target_weights: PortfolioWeights
    current_weights: PortfolioWeights
    trades_needed: Dict[str, float] = Field(default_factory=dict)  # Symbol -> Qty adjustments
    trigger_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class FactorExposure(BaseModel):
    """Asset exposure to macro/style factors."""

    exposures: Dict[str, Dict[str, float]] = Field(default_factory=dict)  # Symbol -> {Factor: Exposure}
    factor_loadings: Dict[str, float] = Field(default_factory=dict)  # Factor -> aggregate weight

    model_config = ConfigDict(frozen=True)


class PortfolioStatistics(BaseModel):
    """Summary statistics for a portfolio."""

    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float

    model_config = ConfigDict(frozen=True)


class PortfolioPerformance(BaseModel):
    """Performance evaluation and attribution summaries."""

    statistics: PortfolioStatistics
    allocation_effect: Dict[str, float] = Field(default_factory=dict)
    selection_effect: Dict[str, float] = Field(default_factory=dict)
    total_attribution: float

    model_config = ConfigDict(frozen=True)


class PortfolioConfiguration(BaseModel):
    """Settings mapping optimization choices."""

    portfolio_id: str
    optimizer_type: str  # MVO, RISK_PARITY, HRP, BLACK_LITTERMAN
    forecast_type: str  # MEAN, MOMENTUM, EWMA
    risk_budget: RiskBudget
    constraints: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
