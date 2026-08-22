"""Thread-safe, append-only repository for storing portfolio allocations and optimizer records.
"""

from __future__ import annotations

import threading
from typing import List, Optional
from research_platform.portfolio_optimizer.interfaces import IPortfolioOptimizerRepository
from research_platform.portfolio_optimizer.models import (
    CorrelationMatrix,
    OptimizerResult,
    PortfolioAllocation,
)


class PortfolioOptimizerRepository(IPortfolioOptimizerRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._allocations: List[PortfolioAllocation] = []
        self._correlations: List[CorrelationMatrix] = []
        self._results: List[OptimizerResult] = []

    def save_allocation(self, allocation: PortfolioAllocation) -> None:
        with self._lock:
            self._allocations.append(allocation)

    def get_latest_allocation(self) -> Optional[PortfolioAllocation]:
        with self._lock:
            if not self._allocations:
                return None
            return self._allocations[-1]

    def save_correlation(self, correlation: CorrelationMatrix) -> None:
        with self._lock:
            self._correlations.append(correlation)

    def get_latest_correlation(self) -> Optional[CorrelationMatrix]:
        with self._lock:
            if not self._correlations:
                return None
            return self._correlations[-1]

    def save_optimizer_result(self, result: OptimizerResult) -> None:
        with self._lock:
            self._results.append(result)

    def list_optimizer_history(self) -> List[OptimizerResult]:
        with self._lock:
            return list(self._results)
