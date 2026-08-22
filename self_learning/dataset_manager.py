"""Thread-safe Dataset Manager for the Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.models.learning_models import DatasetRecord, DatasetStatus, SemanticVersion
from self_learning.metadata import DatasetMetadata
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class DatasetRegistered(BaseModel):
    """Event published when a new dataset is registered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DatasetRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dataset_id: str
    dataset_name: str
    version: str

    model_config = ConfigDict(frozen=True)


class DatasetManager:
    """Thread-safe in-memory Dataset Manager.

    Manages dataset registration, versioning, and metadata.
    No external storage — all data is in-memory only.
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_datasets: int = 500,
        max_versions_per_dataset: int = 20,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._datasets: Dict[str, DatasetRecord] = {}
        self._metadata: Dict[str, DatasetMetadata] = {}
        # name -> list of dataset_ids (ordered by registration time)
        self._name_index: Dict[str, List[str]] = collections.defaultdict(list)
        self._max_datasets = max_datasets
        self._max_versions = max_versions_per_dataset

    def register_dataset(
        self,
        name: str,
        feature_columns: Optional[List[str]] = None,
        target_column: Optional[str] = None,
        row_count: int = 0,
        description: str = "",
        tags: Optional[List[str]] = None,
        schema_metadata: Optional[Dict[str, str]] = None,
        version: Optional[SemanticVersion] = None,
    ) -> DatasetRecord:
        """Register a new dataset version and return its immutable record."""
        with self._lock:
            if len(self._datasets) >= self._max_datasets:
                raise RuntimeError(
                    f"DatasetManager capacity exceeded: cannot register dataset '{name}' "
                    f"(limit={self._max_datasets})."
                )
            cols = feature_columns or []
            ver = version or SemanticVersion()
            record = DatasetRecord(
                name=name,
                version=ver,
                status=DatasetStatus.REGISTERED,
                description=description,
                feature_columns=cols,
                target_column=target_column,
                row_count=row_count,
                column_count=len(cols),
                tags=tags or [],
                schema_metadata=schema_metadata or {},
            )
            self._datasets[record.dataset_id] = record
            self._name_index[name].append(record.dataset_id)

            meta = DatasetMetadata(
                dataset_id=record.dataset_id,
                dataset_name=name,
                version=ver,
                row_count=row_count,
                description=description,
                schema=schema_metadata or {},
            )
            self._metadata[record.dataset_id] = meta

            logger.info("Registered dataset '%s' v%s (id=%s)", name, ver, record.dataset_id)

            if self._event_bus:
                self._event_bus.publish(
                    DatasetRegistered(
                        dataset_id=record.dataset_id,
                        dataset_name=name,
                        version=str(ver),
                    )
                )
            return record

    def get_dataset(self, dataset_id: str) -> Optional[DatasetRecord]:
        """Retrieve a dataset record by its ID."""
        with self._lock:
            return self._datasets.get(dataset_id)

    def get_metadata(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Retrieve metadata for a dataset."""
        with self._lock:
            return self._metadata.get(dataset_id)

    def list_datasets(
        self,
        name: Optional[str] = None,
        status: Optional[DatasetStatus] = None,
    ) -> List[DatasetRecord]:
        """List registered datasets with optional filters."""
        with self._lock:
            records = list(self._datasets.values())
            if name:
                records = [r for r in records if r.name == name]
            if status:
                records = [r for r in records if r.status == status]
            return records

    def get_versions(self, name: str) -> List[DatasetRecord]:
        """Get all registered versions of a dataset by name."""
        with self._lock:
            ids = self._name_index.get(name, [])
            return [self._datasets[did] for did in ids if did in self._datasets]

    def validate_dataset(self, dataset_id: str) -> bool:
        """Validate dataset schema completeness and mark status accordingly."""
        with self._lock:
            record = self._datasets.get(dataset_id)
            if not record:
                return False

            # Validation rule: must have at least one feature column
            passed = len(record.feature_columns) > 0

            new_status = DatasetStatus.VALID if passed else DatasetStatus.INVALID
            updated = DatasetRecord(
                dataset_id=record.dataset_id,
                name=record.name,
                version=record.version,
                status=new_status,
                description=record.description,
                feature_columns=record.feature_columns,
                target_column=record.target_column,
                row_count=record.row_count,
                column_count=record.column_count,
                tags=record.tags,
                schema_metadata=record.schema_metadata,
                created_at=record.created_at,
            )
            self._datasets[dataset_id] = updated
            logger.info("Dataset '%s' validation: %s", dataset_id, new_status.value)
            return passed

    def count(self) -> int:
        """Return count of registered datasets."""
        with self._lock:
            return len(self._datasets)

    def clear(self) -> None:
        """Clear all dataset records."""
        with self._lock:
            self._datasets.clear()
            self._metadata.clear()
            self._name_index.clear()
