"""Metadata Catalog indexing datasets, experiments, and strategies.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.data_platform.models import Dataset, Experiment


class MetadataCatalog:
    """Catalog index registry managing tags and entities lookup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._datasets: Dict[str, Dataset] = {}
        self._experiments: Dict[str, Experiment] = {}
        self._tags: Dict[str, List[str]] = {}

    def register_dataset(self, dataset: Dataset) -> None:
        with self._lock:
            self._datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        with self._lock:
            return self._datasets.get(dataset_id)

    def register_experiment(self, experiment: Experiment) -> None:
        with self._lock:
            self._experiments[experiment.experiment_id] = experiment
            # Index tags
            for tag in experiment.tags:
                if tag not in self._tags:
                    self._tags[tag] = []
                self._tags[tag].append(experiment.experiment_id)

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        with self._lock:
            return self._experiments.get(experiment_id)

    def search_experiments_by_tag(self, tag: str) -> List[str]:
        with self._lock:
            return list(self._tags.get(tag, []))
