"""Thread-safe state store for the Research Platform (Sprint 6)."""

from __future__ import annotations

import collections
import threading
from typing import Dict, List, Optional

from research_platform.core.exceptions import ExperimentError
from research_platform.core.models import ExperimentResult


class ResearchStateStore:
    """Thread-safe, replay-safe state store tracking active research experiment results.

    State Ownership Specification:
    - Purpose: Track transient runtime execution state for active in-flight experiments across threads.
    - Lifetime: Transient in-memory state during runtime execution lifecycle.
    - Ownership: Owns active experiment runtime states. Historical long-term persistence is owned exclusively by ResearchExperimentRepository.
    """

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        self._lock = threading.RLock()
        # Active experiment mapping: experiment_id -> ExperimentResult
        self._experiments: Dict[str, ExperimentResult] = {}
        # Chronological execution queue
        self._history: collections.deque[ExperimentResult] = collections.deque(maxlen=history_limit)

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Retrieve an experiment result by ID."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def save_experiment(self, result: ExperimentResult) -> None:
        """Update or insert an experiment result thread-safely."""
        if not result or not result.experiment_id:
            raise ExperimentError("ExperimentResult must contain a valid experiment_id.")

        with self._lock:
            exp_id = result.experiment_id
            self._experiments[exp_id] = result
            self._history.append(result)

    def list_experiments(self, limit: int = 100) -> List[ExperimentResult]:
        """Retrieve in-memory history of experiment results sorted chronologically."""
        with self._lock:
            return list(self._history)[-limit:]

    def clear(self) -> None:
        """Purge tracked states from memory."""
        with self._lock:
            self._experiments.clear()
            self._history.clear()
