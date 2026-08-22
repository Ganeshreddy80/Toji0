"""Abstract contracts for Portfolio Construction.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.portfolio_construction.models import PortfolioAllocation


class IPortfolioConstructionRepository(abc.ABC):
    """Abstract contract for persisting allocations."""

    @abc.abstractmethod
    def save_allocation(self, allocation: PortfolioAllocation) -> None:
        """Persist target weights allocation details."""

    @abc.abstractmethod
    def get_allocation(self, allocation_id: str) -> Optional[PortfolioAllocation]:
        """Retrieve target weights by ID."""

    @abc.abstractmethod
    def save_correlation_matrix(self, symbol_or_matrix: Any, matrix: Optional[dict[str, dict[str, float]]] = None) -> None:
        """Persist correlation matrix data for a symbol or global map."""

    @abc.abstractmethod
    def get_correlation_matrix(self, symbol: str = "GLOBAL") -> Optional[dict[str, dict[str, float]]]:
        """Retrieve correlation matrix data for a symbol."""
