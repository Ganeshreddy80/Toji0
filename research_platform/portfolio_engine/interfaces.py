"""Abstract contracts for the Portfolio Construction & Risk Engine.
"""

from __future__ import annotations

import abc
import pandas as pd
from typing import Dict, List, Optional

from research_platform.portfolio_engine.models import (
    AllocationResult,
    CovarianceMatrix,
    FactorExposure,
    ForecastResult,
    OptimizationResult,
    Portfolio,
    PortfolioPerformance,
    PortfolioWeights,
    RebalancePlan,
    RiskBudget,
    RiskContribution
)


class IPortfolioRepository(abc.ABC):
    """Abstract database repository contract for portfolios persistence."""

    @abc.abstractmethod
    def save_portfolio(self, portfolio: Portfolio) -> None:
        """Persist a Portfolio."""

    @abc.abstractmethod
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Fetch Portfolio by ID."""


class IPortfolioAllocator(abc.ABC):
    """Abstract contract for weight allocating rules."""

    @abc.abstractmethod
    def allocate(self, symbols: List[str], returns_df: pd.DataFrame) -> AllocationResult:
        """Allocate weights over symbols based on defined sizing logic."""


class IPortfolioOptimizer(abc.ABC):
    """Abstract contract for portfolio optimizing engines."""

    @abc.abstractmethod
    def optimize(
        self,
        symbols: List[str],
        forecast: ForecastResult,
        covariance: CovarianceMatrix
    ) -> OptimizationResult:
        """Calculate optimized weight allocations under objective choices."""


class ICovarianceEngine(abc.ABC):
    """Abstract contract for estimating asset returns covariances."""

    @abc.abstractmethod
    def calculate_covariance(self, returns_df: pd.DataFrame) -> CovarianceMatrix:
        """Estimate return covariances across returns matrix DataFrame."""


class IForecastEngine(abc.ABC):
    """Abstract contract for forecasting expected returns."""

    @abc.abstractmethod
    def forecast_returns(self, price_df: pd.DataFrame) -> ForecastResult:
        """Estimate future expected returns from price history."""


class IFactorModel(abc.ABC):
    """Abstract contract for evaluating factors exposures."""

    @abc.abstractmethod
    def calculate_exposures(self, weights: PortfolioWeights, returns_df: pd.DataFrame) -> FactorExposure:
        """Compute portfolio exposure weights against size, momentum, value factors."""


class IRiskBudget(abc.ABC):
    """Abstract contract for risk budget checks."""

    @abc.abstractmethod
    def calculate_risk_contributions(self, weights: PortfolioWeights, cov: CovarianceMatrix) -> RiskContribution:
        """Calculate marginal and component risk contributions across assets."""


class IConstraintEngine(abc.ABC):
    """Abstract contract for evaluating portfolio transaction limits."""

    @abc.abstractmethod
    def check_constraints(self, weights: PortfolioWeights) -> List[Any]:
        """Verify allocation weights against leverage, sector, or max/min constraints."""


class IRebalancer(abc.ABC):
    """Abstract contract for rebalancing trigger evaluations."""

    @abc.abstractmethod
    def evaluate_rebalance(self, current: PortfolioWeights, target: PortfolioWeights) -> Optional[RebalancePlan]:
        """Evaluate if drift triggers or calendar updates require rebalance executions."""


class IPerformanceAttribution(abc.ABC):
    """Abstract contract for attribution reports."""

    @abc.abstractmethod
    def calculate_attribution(
        self,
        portfolio_weights: PortfolioWeights,
        benchmark_weights: PortfolioWeights,
        portfolio_returns: Dict[str, float],
        benchmark_returns: Dict[str, float]
    ) -> PortfolioPerformance:
        """Calculate Brinson-Fachler allocation and selection effects."""
