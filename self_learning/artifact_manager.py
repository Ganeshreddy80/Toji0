"""Thread-safe In-Memory Artifact Manager for the Self Learning Engine (Sprint 11B)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.training_events import ArtifactRegistered
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class ArtifactRecord(BaseModel):
    """Immutable record of a training artifact."""

    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Artifact name.")
    version: str = Field(default="1.0.0", description="Artifact version string.")
    pipeline_id: str = Field(..., description="Associated pipeline identifier.")
    artifact_type: str = Field(default="model_weights", description="Type of artifact.")
    uri_or_payload: Any = Field(default=None, description="In-memory artifact content or URI.")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ArtifactManager:
    """Thread-safe in-memory Artifact Manager."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_artifacts: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_artifacts = max_artifacts
        # artifact_id -> ArtifactRecord
        self._artifacts: Dict[str, ArtifactRecord] = {}
        # (name, version) -> artifact_id
        self._version_index: Dict[tuple, str] = {}
        # pipeline_id -> list of artifact_ids
        self._pipeline_index: Dict[str, List[str]] = collections.defaultdict(list)

    def register_artifact(
        self,
        name: str,
        pipeline_id: str,
        artifact_type: str = "model_weights",
        version: str = "1.0.0",
        uri_or_payload: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactRecord:
        """Register a new artifact."""
        with self._lock:
            if len(self._artifacts) >= self._max_artifacts:
                oldest_id = next(iter(self._artifacts))
                self.delete_artifact(oldest_id)

            record = ArtifactRecord(
                name=name,
                version=version,
                pipeline_id=pipeline_id,
                artifact_type=artifact_type,
                uri_or_payload=uri_or_payload,
                metadata=metadata or {},
            )
            self._artifacts[record.artifact_id] = record
            self._version_index[(name, version)] = record.artifact_id
            self._pipeline_index[pipeline_id].append(record.artifact_id)

            logger.info("Registered artifact '%s' v%s (id=%s) for pipeline '%s'", name, version, record.artifact_id, pipeline_id)

            if self._event_bus:
                self._event_bus.publish(
                    ArtifactRegistered(
                        artifact_id=record.artifact_id,
                        pipeline_id=pipeline_id,
                        artifact_name=name,
                        version=version,
                    )
                )
            return record

    def retrieve_artifact(self, artifact_id: str) -> Optional[ArtifactRecord]:
        """Retrieve an artifact by ID."""
        with self._lock:
            return self._artifacts.get(artifact_id)

    def get_by_name_and_version(self, name: str, version: str) -> Optional[ArtifactRecord]:
        """Retrieve an artifact by name and version."""
        with self._lock:
            aid = self._version_index.get((name, version))
            if not aid:
                return None
            return self._artifacts.get(aid)

    def list_artifacts(self, pipeline_id: Optional[str] = None) -> List[ArtifactRecord]:
        """List all artifacts, optionally filtered by pipeline_id."""
        with self._lock:
            if pipeline_id:
                aids = self._pipeline_index.get(pipeline_id, [])
                return [self._artifacts[aid] for aid in aids if aid in self._artifacts]
            return list(self._artifacts.values())

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact by ID."""
        with self._lock:
            record = self._artifacts.pop(artifact_id, None)
            if record is None:
                return False
            self._version_index.pop((record.name, record.version), None)
            aids = self._pipeline_index.get(record.pipeline_id, [])
            if artifact_id in aids:
                aids.remove(artifact_id)
            logger.info("Deleted artifact '%s'", artifact_id)
            return True

    def count(self) -> int:
        """Return count of stored artifacts."""
        with self._lock:
            return len(self._artifacts)

    def clear(self) -> None:
        """Clear all stored artifacts."""
        with self._lock:
            self._artifacts.clear()
            self._version_index.clear()
            self._pipeline_index.clear()
