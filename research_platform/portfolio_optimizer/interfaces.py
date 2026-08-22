"""Abstract contracts for the Meta Portfolio Optimizer.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from research_platform.portfolio_optimizer.models import (
    CorrelationMatrix,
    OptimizerResult,
    PortfolioAllocation,
    RiskBudget,
)


class IPortfolioOptimizerRepository(abc.ABC):
    """Abstract contract for persisting and retrieving optimization results and logs."""

    @abc.abstractmethod
    def save_allocation(self, allocation: PortfolioAllocation) -> None:
        """Persist a portfolio allocation record."""

    @abc.abstractmethod
    def get_latest_allocation(self) -> Optional[PortfolioAllocation]:
        """Retrieve the latest portfolio allocation weights."""

    @abc.abstractmethod
    def save_correlation(self, correlation: CorrelationMatrix) -> None:
        """Persist a correlation matrix log."""

    @abc.abstractmethod
    def get_latest_correlation(self) -> Optional[CorrelationMatrix]:
        """Retrieve the latest correlation matrix log."""

    @abc.abstractmethod
    def save_optimizer_result(self, result: OptimizerResult) -> None:
        """Persist optimization calculation statistics."""

    @abc.abstractmethod
    def list_optimizer_history(self) -> List[OptimizerResult]:
        """List historical optimization outputs."""


class ICorrelationEngine(abc.ABC):
    """Abstract contract for computing strategy correlations."""

    @abc.abstractmethod
    def calculate_correlation(self, returns_data: Dict[str, List[float]]) -> CorrelationMatrix:
        """Compute strategy-to-strategy correlation matrix."""


class IRiskBudgeter(abc.ABC):
    """Abstract contract for assigning and verifying risk budgets."""

    @abc.abstractmethod
    def evaluate_risk_budget(self, weights: Dict[str, float], covariance: List[List[float]], limits: Dict[str, float]) -> RiskBudget:
        """Evaluate marginal risk contributions and verify budget limits."""


class IPortfolioOptimizationEngine(abc.ABC):
    """Abstract contract for weight optimization solvers."""

    @abc.abstractmethod
    def optimize_portfolio(
        self,
        symbols: List[str],
        returns_data: Dict[str, List[float]],
        target_risk: float = 0.5,
        min_weight: float = 0.0,
        max_weight: float = 1.0
    ) -> OptimizerResult:
        """Compute optimal asset weights."""


class IPortfolioOptimizerOrchestrator(abc.ABC):
    """Abstract contract for the portfolio optimizer orchestrator."""
    pass
