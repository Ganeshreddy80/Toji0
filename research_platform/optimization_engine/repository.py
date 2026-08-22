"""Database repository saving optimization runs and trial histories.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.optimization_engine.interfaces import IOptimizationRepository
from research_platform.optimization_engine.models import OptimizationRun, OptimizationTrial


class OptimizationRepository(IOptimizationRepository):
    """Memory database repository for optimization runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, OptimizationRun] = {}
        self._trials: Dict[str, List[OptimizationTrial]] = {}

    def save_run(self, run: OptimizationRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[OptimizationRun]:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> List[OptimizationRun]:
        with self._lock:
            return list(self._runs.values())

    def save_trial(self, run_id: str, trial: OptimizationTrial) -> None:
        with self._lock:
            if run_id not in self._trials:
                self._trials[run_id] = []
            self._trials[run_id].append(trial)

    def list_trials(self, run_id: str) -> List[OptimizationTrial]:
        with self._lock:
            return list(self._trials.get(run_id, []))
