"""Abstract contracts for the Research Data Platform.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.data_platform.models import (
    DataQualityReport,
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    LineageRecord
)


class IDataPlatformRepository(abc.ABC):
    """Abstract database repository contract for data platform persistence."""

    @abc.abstractmethod
    def save_dataset(self, dataset: Dataset) -> None:
        """Persist a Dataset."""

    @abc.abstractmethod
    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Fetch Dataset by ID."""

    @abc.abstractmethod
    def save_version(self, version: DatasetVersion) -> None:
        """Persist a DatasetVersion."""

    @abc.abstractmethod
    def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        """Fetch DatasetVersion by ID."""


class ILineageEngine(abc.ABC):
    """Abstract contract for tracking upstream/downstream dependency lineage."""

    @abc.abstractmethod
    def register_lineage(self, record: LineageRecord) -> None:
        """Register source dependency lineage record."""

    @abc.abstractmethod
    def get_upstream(self, target_id: str) -> List[str]:
        """Traverse upstream dependency target IDs."""


class IDataQualityEngine(abc.ABC):
    """Abstract contract for dataset quality validation gates."""

    @abc.abstractmethod
    def evaluate_quality(self, version_id: str, df: Any) -> DataQualityReport:
        """Run validation gates checks and calculate quality scores."""
