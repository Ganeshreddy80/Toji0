"""Thread-safe memory repository caching portfolio construction allocations.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.portfolio_construction.interfaces import IPortfolioConstructionRepository
from research_platform.portfolio_construction.models import PortfolioAllocation


class PortfolioConstructionRepository(IPortfolioConstructionRepository):
    """Memory-backed, thread-safe repository for portfolio allocations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._allocations: Dict[str, PortfolioAllocation] = {}
        self._matrices: Dict[str, Dict[str, Dict[str, float]]] = {}

    def save_allocation(self, allocation: PortfolioAllocation) -> None:
        with self._lock:
            self._allocations[allocation.allocation_id] = allocation

    def get_allocation(self, allocation_id: str) -> Optional[PortfolioAllocation]:
        with self._lock:
            return self._allocations.get(allocation_id)

    def save_correlation_matrix(self, symbol_or_matrix: Any, matrix: Optional[dict[str, dict[str, float]]] = None) -> None:
        with self._lock:
            if isinstance(symbol_or_matrix, dict) and matrix is None:
                self._matrices["GLOBAL"] = symbol_or_matrix
            elif isinstance(symbol_or_matrix, str) and matrix is not None:
                self._matrices[symbol_or_matrix] = matrix
            elif matrix is not None:
                self._matrices[str(symbol_or_matrix)] = matrix

    def get_correlation_matrix(self, symbol: str = "GLOBAL") -> Optional[dict[str, dict[str, float]]]:
        with self._lock:
            return self._matrices.get(symbol) or self._matrices.get("GLOBAL")
