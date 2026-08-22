"""Abstract contracts for the Experiment Management Platform.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.experiment_management.models import (
    ExperimentComparison,
    ExperimentRecord,
    ReproducibilityCheck,
)


class IExperimentRepository(abc.ABC):
    """Abstract contract for persisting and retrieving alpha experiments metrics."""

    @abc.abstractmethod
    def save_experiment(self, record: ExperimentRecord) -> None:
        """Persist an experiment record."""

    @abc.abstractmethod
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """Retrieve an experiment record by ID."""

    @abc.abstractmethod
    def list_experiments(self) -> List[ExperimentRecord]:
        """List all registered experiment records."""

    @abc.abstractmethod
    def save_reproducibility_check(self, check: ReproducibilityCheck) -> None:
        """Persist a reproducibility check result."""

    @abc.abstractmethod
    def list_reproducibility_checks(self, experiment_id: str) -> List[ReproducibilityCheck]:
        """List historical reproducibility checks for an experiment."""

    @abc.abstractmethod
    def save_comparison(self, comparison: ExperimentComparison) -> None:
        """Persist a comparison report."""

    @abc.abstractmethod
    def get_latest_comparison(self) -> Optional[ExperimentComparison]:
        """Retrieve the latest comparative report."""


class IExperimentReplayer(abc.ABC):
    """Abstract contract for executing and verifying experiment replays."""

    @abc.abstractmethod
    def replay_experiment(self, original: ExperimentRecord, replayed_metrics: Dict[str, float], replayed_code_hash: str) -> ReproducibilityCheck:
        """Verify metric variances and code hash matches between run logs."""


class IExperimentComparer(abc.ABC):
    """Abstract contract for compiling comparative parameter diffs."""

    @abc.abstractmethod
    def compare_experiments(self, records: List[ExperimentRecord]) -> ExperimentComparison:
        """Compile parameters diff and output comparative matrices."""


class IExperimentManagementOrchestrator(abc.ABC):
    """Abstract contract for the experiment manager orchestrator."""
    pass
