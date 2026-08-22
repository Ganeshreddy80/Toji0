"""Protocols and Interfaces for the Portfolio Construction Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Protocol, Tuple, runtime_checkable

from portfolio_construction.core.enums import OptimizationObjective
from portfolio_construction.core.models import (
    PortfolioCandidate,
    PortfolioConstraintConfig,
    PortfolioConstructionSnapshot,
    PortfolioConstructionState,
    TargetPortfolio,
)


@runtime_checkable
class ICorrelationFilter(Protocol):
    """Protocol for filtering candidate signals based on correlation thresholds."""

    def filter_candidates(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Dict[str, Dict[str, float]],
        max_correlation: float,
    ) -> Tuple[List[PortfolioCandidate], List[str]]:
        """
        Filter candidate setups exceeding pairwise correlation thresholds.
        Returns tuple of (accepted_candidates, rejected_symbols).
        """
        ...


@runtime_checkable
class IDiversificationEngine(Protocol):
    """Protocol for enforcing position count and sector diversification limits."""

    def apply_diversification(
        self,
        candidates: List[PortfolioCandidate],
        config: PortfolioConstraintConfig,
    ) -> Tuple[List[PortfolioCandidate], List[str]]:
        """
        Enforce max positions and sector exposure caps.
        Returns tuple of (diversified_candidates, rejected_symbols).
        """
        ...


@runtime_checkable
class IPortfolioConstraintEngine(Protocol):
    """Protocol for validating candidate sets and allocation weights against constraints."""

    def validate_constraints(
        self,
        candidates: List[PortfolioCandidate],
        weights: Dict[str, float],
        config: PortfolioConstraintConfig,
    ) -> Tuple[bool, List[str]]:
        """
        Validate portfolio target weights against all defined constraints.
        Returns tuple of (is_valid, list_of_violation_reasons).
        """
        ...


@runtime_checkable
class IPortfolioOptimizer(Protocol):
    """Protocol for calculating optimal target weights across candidate assets."""

    def optimize(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Dict[str, Dict[str, float]],
        config: PortfolioConstraintConfig,
        objective: OptimizationObjective = OptimizationObjective.CONFIDENCE_WEIGHTED,
    ) -> Dict[str, float]:
        """
        Calculate normalized target weights [0.0, 1.0] for candidate assets.
        Returns dictionary mapping symbol -> target_weight.
        """
        ...


@runtime_checkable
class IPortfolioConstructionEngine(Protocol):
    """Protocol for overall portfolio construction coordination."""

    def construct_portfolio(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        config: Optional[PortfolioConstraintConfig] = None,
        objective: OptimizationObjective = OptimizationObjective.CONFIDENCE_WEIGHTED,
    ) -> TargetPortfolio:
        """Construct an institutional target portfolio from strategy setup candidates."""
        ...


@runtime_checkable
class IPortfolioConstructionStateStore(Protocol):
    """Protocol for thread-safe state storage of portfolio construction decisions."""

    def update_state(self, state_update: PortfolioConstructionState) -> PortfolioConstructionSnapshot:
        """Store or update the current portfolio construction state."""
        ...

    def get_state(self, symbol: str = "PORTFOLIO") -> Optional[PortfolioConstructionState]:
        """Retrieve current portfolio construction state."""
        ...

    def clear(self) -> None:
        """Clear stored state."""
        ...


@runtime_checkable
class IPortfolioConstructionRepository(Protocol):
    """Protocol for snapshot and correlation matrix persistence."""

    def save_snapshot(self, snapshot: PortfolioConstructionSnapshot) -> None:
        """Persist a portfolio construction snapshot."""
        ...

    def load_latest_snapshot(self, symbol: str = "PORTFOLIO") -> Optional[PortfolioConstructionSnapshot]:
        """Load the latest snapshot for a portfolio symbol."""
        ...

    def save_correlation_matrix(self, symbol: str, matrix: Dict[str, Dict[str, float]]) -> None:
        """Persist a correlation matrix for a symbol."""
        ...

    def get_correlation_matrix(self, symbol: str) -> Optional[Dict[str, Dict[str, float]]]:
        """Retrieve a correlation matrix for a symbol."""
        ...
