"""Immutable dataset manager for the Research Platform (Sprint 6)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from research_platform.core.exceptions import DatasetError
from research_platform.core.interfaces import IDatasetManager
from research_platform.core.models import DatasetVersion

logger = logging.getLogger(__name__)


class DatasetManager(IDatasetManager):
    """Thread-safe manager for immutable market research dataset versions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # key: (dataset_id, version) -> DatasetVersion
        self._datasets: Dict[tuple[str, str], DatasetVersion] = {}
        # latest mapping: dataset_id -> DatasetVersion
        self._latest: Dict[str, DatasetVersion] = {}

    def register_dataset(self, dataset: DatasetVersion) -> None:
        """Register an immutable dataset version."""
        if not dataset or not dataset.dataset_id or not dataset.version:
            raise DatasetError("DatasetVersion must contain valid dataset_id and version.")

        with self._lock:
            key = (dataset.dataset_id, dataset.version)
            if key in self._datasets:
                logger.info("DatasetManager: Dataset '%s' version '%s' already registered. Overwriting.", dataset.dataset_id, dataset.version)

            self._datasets[key] = dataset
            self._latest[dataset.dataset_id] = dataset
            logger.info("DatasetManager: Registered dataset '%s' version '%s'", dataset.dataset_id, dataset.version)

    def get_dataset(self, dataset_id: str, version: Optional[str] = None) -> Optional[DatasetVersion]:
        """Fetch a dataset version by ID and optional version string."""
        with self._lock:
            if version:
                return self._datasets.get((dataset_id, version))
            return self._latest.get(dataset_id)

    def list_datasets(self) -> List[DatasetVersion]:
        """List all registered dataset versions."""
        with self._lock:
            return list(self._datasets.values())
