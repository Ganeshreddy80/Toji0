"""Thread-safe, append-only repository for storing experiment records and checks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.experiment_management.interfaces import IExperimentRepository
from research_platform.experiment_management.models import (
    ExperimentComparison,
    ExperimentRecord,
    ReproducibilityCheck,
)


class ExperimentRepository(IExperimentRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, ExperimentRecord] = {}
        self._checks: Dict[str, List[ReproducibilityCheck]] = {}
        self._comparisons: List[ExperimentComparison] = []

    def save_experiment(self, record: ExperimentRecord) -> None:
        with self._lock:
            self._records[record.experiment_id] = record

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        with self._lock:
            return self._records.get(experiment_id)

    def list_experiments(self) -> List[ExperimentRecord]:
        with self._lock:
            return list(self._records.values())

    def save_reproducibility_check(self, check: ReproducibilityCheck) -> None:
        with self._lock:
            exp_id = check.experiment_id
            if exp_id not in self._checks:
                self._checks[exp_id] = []
            self._checks[exp_id].append(check)

    def list_reproducibility_checks(self, experiment_id: str) -> List[ReproducibilityCheck]:
        with self._lock:
            return list(self._checks.get(experiment_id, []))

    def save_comparison(self, comparison: ExperimentComparison) -> None:
        with self._lock:
            self._comparisons.append(comparison)

    def get_latest_comparison(self) -> Optional[ExperimentComparison]:
        with self._lock:
            if not self._comparisons:
                return None
            return self._comparisons[-1]
