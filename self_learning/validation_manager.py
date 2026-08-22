"""Thread-safe Validation Dataset Manager for the Self Learning Engine (Sprint 11C)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.models.learning_models import SemanticVersion

logger = logging.getLogger(__name__)


class ValidationDatasetRecord(BaseModel):
    """Immutable record of a validation dataset."""

    dataset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Validation dataset name.")
    version: SemanticVersion = Field(default_factory=SemanticVersion)
    feature_columns: List[str] = Field(default_factory=list)
    target_column: Optional[str] = Field(default=None)
    row_count: int = Field(default=0, ge=0)
    schema_metadata: Dict[str, str] = Field(default_factory=dict)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ValidationManager:
    """Thread-safe manager for validation datasets and model schema compatibility checks."""

    def __init__(self, max_datasets: int = 500) -> None:
        self._lock = threading.RLock()
        self._max_datasets = max_datasets
        # dataset_id -> ValidationDatasetRecord
        self._datasets: Dict[str, ValidationDatasetRecord] = {}
        # name -> list of dataset_ids
        self._name_index: Dict[str, List[str]] = collections.defaultdict(list)

    def register_validation_dataset(
        self,
        name: str,
        feature_columns: Optional[List[str]] = None,
        target_column: Optional[str] = None,
        row_count: int = 0,
        schema_metadata: Optional[Dict[str, str]] = None,
        description: str = "",
        version: Optional[SemanticVersion] = None,
    ) -> ValidationDatasetRecord:
        """Register a new validation dataset."""
        with self._lock:
            if len(self._datasets) >= self._max_datasets:
                raise RuntimeError(f"ValidationManager capacity exceeded: limit={self._max_datasets}")

            ver = version or SemanticVersion()
            cols = feature_columns or []
            record = ValidationDatasetRecord(
                name=name,
                version=ver,
                feature_columns=cols,
                target_column=target_column,
                row_count=row_count,
                schema_metadata=schema_metadata or {},
                description=description,
            )

            self._datasets[record.dataset_id] = record
            self._name_index[name].append(record.dataset_id)

            logger.info("Registered validation dataset '%s' v%s (id=%s)", name, ver, record.dataset_id)
            return record

    def get_dataset(self, dataset_id: str) -> Optional[ValidationDatasetRecord]:
        """Retrieve a validation dataset by ID."""
        with self._lock:
            return self._datasets.get(dataset_id)

    def get_by_name(self, name: str) -> List[ValidationDatasetRecord]:
        """Get all registered versions of a dataset by name."""
        with self._lock:
            ids = self._name_index.get(name, [])
            return [self._datasets[did] for did in ids if did in self._datasets]

    def list_datasets(self) -> List[ValidationDatasetRecord]:
        """List all registered validation datasets."""
        with self._lock:
            return list(self._datasets.values())

    def validate_compatibility(
        self,
        required_features: List[str],
        dataset_id: str,
    ) -> Tuple[bool, List[str]]:
        """Validate if a model's required feature columns exist in the validation dataset."""
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return False, [f"Validation dataset '{dataset_id}' not found"]

            available = set(ds.feature_columns)
            missing = [col for col in required_features if col not in available]

            if missing:
                return False, [f"Dataset missing required features: {missing}"]

            return True, []

    def count(self) -> int:
        """Return count of registered datasets."""
        with self._lock:
            return len(self._datasets)

    def clear(self) -> None:
        """Clear all validation datasets."""
        with self._lock:
            self._datasets.clear()
            self._name_index.clear()
