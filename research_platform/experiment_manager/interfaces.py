"""Abstract contracts for the Experiment Manager.
"""

from __future__ import annotations

import abc
from typing import Dict, Any, List, Optional
from research_platform.experiment_manager.models import (
    Experiment,
    ExperimentComparison,
    Leaderboard,
    ReproducibilitySnapshot,
)


class IExperimentRepository(abc.ABC):
    """Abstract contract for persisting research experiments."""

    @abc.abstractmethod
    def save_experiment(self, experiment: Experiment) -> None:
        """Persist experiment configurations and results."""

    @abc.abstractmethod
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Retrieve experiment details by ID."""

    @abc.abstractmethod
    def list_experiments(self) -> List[Experiment]:
        """List all experiments."""


class IExperimentManager(abc.ABC):
    """Abstract contract for core Experiment Manager orchestrators."""

    @abc.abstractmethod
    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        tags: List[str],
        group_id: str,
        reproducibility: ReproducibilitySnapshot
    ) -> Experiment:
        """Create new experiment, validating inputs."""


class IComparisonEngine(abc.ABC):
    """Abstract contract for comparing metrics across multiple experiments."""

    @abc.abstractmethod
    def compare_runs(self, experiment_ids: List[str]) -> ExperimentComparison:
        """Compare results and parameters maps across runs."""


class IRankingEngine(abc.ABC):
    """Abstract contract for leaderboard sorting."""

    @abc.abstractmethod
    def rank_strategies(self, name: str, experiments: List[Experiment]) -> Leaderboard:
        """Score and sort strategies into ranked leaderboard entries."""


class IReproducibilityEngine(abc.ABC):
    """Abstract contract for verifying seed snapshots reproducibility."""

    @abc.abstractmethod
    def verify_reproducibility(self, first: ReproducibilitySnapshot, second: ReproducibilitySnapshot) -> bool:
        """Verify parameters matching to validate exact replay safety."""
