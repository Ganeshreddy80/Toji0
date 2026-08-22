"""Abstract contracts for the Optimization Engine.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.optimization_engine.models import (
    OptimizationConfiguration,
    OptimizationRun,
    ParameterCombination
)


class IOptimizationRepository(abc.ABC):
    """Abstract database repository contract for optimization persistence."""

    @abc.abstractmethod
    def save_run(self, run: OptimizationRun) -> None:
        """Persist an OptimizationRun."""

    @abc.abstractmethod
    def get_run(self, run_id: str) -> Optional[OptimizationRun]:
        """Fetch OptimizationRun by ID."""

    @abc.abstractmethod
    def list_runs(self) -> List[OptimizationRun]:
        """List all runs."""


class IOptimizer(abc.ABC):
    """Abstract contract for parameter search algorithms."""

    @abc.abstractmethod
    def generate_combinations(self, config: OptimizationConfiguration) -> List[ParameterCombination]:
        """Generate parameter combinations to evaluate."""
