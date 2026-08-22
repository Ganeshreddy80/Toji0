"""Thread-safe Feature Store with bounded memory for the Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.models.learning_models import FeatureRecord, FeatureType
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class FeatureUpdated(BaseModel):
    """Event published when a feature value is updated in the store."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="FeatureUpdated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    feature_id: str
    feature_name: str
    feature_type: str

    model_config = ConfigDict(frozen=True)


class FeatureStore:
    """Thread-safe bounded Feature Store.

    Supports up to `max_features` features, each with a bounded history
    of `max_history_per_feature` past values. Feature lookups are O(1).
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_features: int = 1000,
        max_history_per_feature: int = 100,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_features = max_features
        self._max_history = max_history_per_feature
        # feature_id -> current FeatureRecord
        self._features: Dict[str, FeatureRecord] = {}
        # feature_name -> feature_id (fast name lookup)
        self._name_index: Dict[str, str] = {}
        # feature_id -> bounded deque of historical FeatureRecords
        self._history: Dict[str, collections.deque] = {}

    def register_feature(
        self,
        name: str,
        feature_type: FeatureType = FeatureType.NUMERIC,
        initial_value: Any = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        source_dataset_id: Optional[str] = None,
    ) -> FeatureRecord:
        """Register a new feature in the store."""
        with self._lock:
            if name in self._name_index:
                # Return existing feature rather than duplicate
                existing_id = self._name_index[name]
                return self._features[existing_id]

            record = FeatureRecord(
                name=name,
                feature_type=feature_type,
                value=initial_value,
                description=description,
                tags=tags or [],
                source_dataset_id=source_dataset_id,
            )
            self._features[record.feature_id] = record
            self._name_index[name] = record.feature_id
            self._history[record.feature_id] = collections.deque(maxlen=self._max_history)
            logger.info("Registered feature '%s' (id=%s, type=%s)", name, record.feature_id, feature_type.value)
            return record

    def update_feature(
        self,
        name: str,
        value: Any,
    ) -> Optional[FeatureRecord]:
        """Update the value of an existing feature. Records prior value in history.

        Feature lookup is O(1) via name index, satisfying the <10ms SLA.
        """
        start_t = time.perf_counter()
        with self._lock:
            feature_id = self._name_index.get(name)
            if feature_id is None:
                logger.warning("update_feature: feature '%s' not found", name)
                return None

            existing = self._features[feature_id]
            # Archive current record to history
            self._history[feature_id].append(existing)

            # Create updated immutable record
            updated = FeatureRecord(
                feature_id=existing.feature_id,
                name=existing.name,
                feature_type=existing.feature_type,
                value=value,
                description=existing.description,
                tags=existing.tags,
                source_dataset_id=existing.source_dataset_id,
                created_at=existing.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._features[feature_id] = updated

            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            logger.debug("Feature '%s' updated in %.3f ms", name, elapsed_ms)

            if self._event_bus:
                self._event_bus.publish(
                    FeatureUpdated(
                        feature_id=feature_id,
                        feature_name=name,
                        feature_type=existing.feature_type.value,
                    )
                )
            return updated

    def retrieve_feature(self, name: str) -> Optional[FeatureRecord]:
        """Retrieve the current feature record by name. O(1) lookup."""
        with self._lock:
            feature_id = self._name_index.get(name)
            if feature_id is None:
                return None
            return self._features.get(feature_id)

    def get_feature_by_id(self, feature_id: str) -> Optional[FeatureRecord]:
        """Retrieve feature record by its UUID."""
        with self._lock:
            return self._features.get(feature_id)

    def get_feature_history(self, name: str) -> List[FeatureRecord]:
        """Return ordered history of prior values for a feature."""
        with self._lock:
            feature_id = self._name_index.get(name)
            if feature_id is None:
                return []
            return list(self._history.get(feature_id, []))

    def list_features(self, feature_type: Optional[FeatureType] = None) -> List[FeatureRecord]:
        """List all registered features, optionally filtered by type."""
        with self._lock:
            records = list(self._features.values())
            if feature_type:
                records = [r for r in records if r.feature_type == feature_type]
            return records

    def count(self) -> int:
        """Return count of registered features."""
        with self._lock:
            return len(self._features)

    def clear(self) -> None:
        """Clear all feature records and history."""
        with self._lock:
            self._features.clear()
            self._name_index.clear()
            self._history.clear()
