"""Persistence repository for the Research Platform (Sprint 6)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, List, Optional

from research_platform.core.exceptions import RepositoryError
from research_platform.core.interfaces import IExperimentRepository
from research_platform.core.models import ExperimentResult

logger = logging.getLogger(__name__)


class ResearchExperimentRepository(IExperimentRepository):
    """Thread-safe, atomic persistence layer for experiment configurations, dataset versions, and results.

    State Ownership Document:
    - ResearchStateStore: Owns transient runtime execution state tracking active/in-flight experiments across threads.
    - ResearchExperimentRepository: Owns persisted experiment history and query indexes across system sessions.
    """

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        self._by_id: dict[str, ExperimentResult] = {}
        self._history: list[ExperimentResult] = []
        self._lock = threading.RLock()

    def save_experiment(self, result: ExperimentResult) -> None:
        """Persist an experiment result atomically.

        Option A Pattern:
        1. Write to persistent storage engine first (if configured).
        2. If storage succeeds, commit to in-memory cache and history under lock.
        3. If storage fails, raise RepositoryError without committing to memory.
        """
        if not result or not result.experiment_id:
            raise RepositoryError("ExperimentResult must contain a valid experiment_id.")

        # 1. Persist to storage engine first (Option A - Atomic Persistence)
        if self._storage:
            try:
                row = {
                    "experiment_id": result.experiment_id,
                    "name": result.config.name,
                    "dataset_id": result.config.dataset_version.dataset_id,
                    "dataset_version": result.config.dataset_version.version,
                    "strategy_id": result.config.strategy_version.strategy_id,
                    "strategy_version": result.config.strategy_version.version,
                    "status": result.status.value,
                    "completed_at": result.completed_at.isoformat(),
                    "data": result.model_dump_json(),
                }
                self._storage.write_rows("research_experiments", [row])
            except Exception as e:
                logger.error("ResearchRepository: Failed to write experiment row: %s", e)
                raise RepositoryError(f"Failed to persist experiment to storage: {e}") from e

        # 2. Commit to memory cache only after successful storage write
        with self._lock:
            exp_id = result.experiment_id
            self._by_id[exp_id] = result
            self._history.append(result)

            # Bounded memory cache eviction: remove oldest history item and purge _by_id key if unreferenced
            if len(self._history) > 1000:
                removed = self._history.pop(0)
                if not any(item.experiment_id == removed.experiment_id for item in self._history):
                    self._by_id.pop(removed.experiment_id, None)

    def load_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Load an experiment result by ID."""
        with self._lock:
            if experiment_id in self._by_id:
                return self._by_id[experiment_id]

        if self._storage:
            try:
                query = "SELECT data FROM research_experiments WHERE experiment_id = %s"
                rows = self._storage.execute(query, (experiment_id,))
                if rows and isinstance(rows, (list, tuple)):
                    raw_data = rows[0].get("data") if isinstance(rows[0], dict) else None
                    if raw_data:
                        data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                        result = ExperimentResult(**data_dict)
                        with self._lock:
                            self._by_id[experiment_id] = result
                        return result
            except Exception as e:
                logger.error("ResearchRepository: Failed to load experiment %s: %s", experiment_id, e)
                raise RepositoryError(f"Failed to load experiment from storage: {e}") from e

        return None

    def list_experiments(self) -> List[ExperimentResult]:
        """Retrieve all experiment results."""
        with self._lock:
            return list(self._history)
