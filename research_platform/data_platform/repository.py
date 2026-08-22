"""Database repository saving datasets, versions, and experiment runs.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.data_platform.interfaces import IDataPlatformRepository
from research_platform.data_platform.models import (
    DataQualityReport,
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    LineageRecord
)


class DataPlatformRepository(IDataPlatformRepository):
    """Memory database repository for research datasets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._datasets: Dict[str, Dataset] = {}
        self._versions: Dict[str, DatasetVersion] = {}
        self._experiments: Dict[str, Experiment] = {}
        self._runs: Dict[str, ExperimentRun] = {}
        self._lineages: Dict[str, LineageRecord] = {}
        self._quality_reports: Dict[str, DataQualityReport] = {}

    def save_dataset(self, dataset: Dataset) -> None:
        with self._lock:
            self._datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        with self._lock:
            return self._datasets.get(dataset_id)

    def save_version(self, version: DatasetVersion) -> None:
        with self._lock:
            self._versions[version.version_id] = version

    def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        with self._lock:
            return self._versions.get(version_id)

    def save_experiment(self, experiment: Experiment) -> None:
        with self._lock:
            self._experiments[experiment.experiment_id] = experiment

    def save_run(self, run: ExperimentRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def save_lineage(self, record: LineageRecord) -> None:
        with self._lock:
            self._lineages[record.lineage_id] = record

    def save_quality_report(self, report: DataQualityReport) -> None:
        with self._lock:
            self._quality_reports[report.report_id] = report
