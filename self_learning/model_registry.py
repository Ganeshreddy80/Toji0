"""Thread-safe Model Registry for the Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.models.learning_models import ModelRecord, ModelStatus, SemanticVersion
from self_learning.model_versioning import ModelVersioning
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class ModelRegistered(BaseModel):
    """Event published when a new ML model is registered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ModelRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_id: str
    model_name: str
    version: str

    model_config = ConfigDict(frozen=True)


class ModelActivated(BaseModel):
    """Event published when a model version is activated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ModelActivated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_id: str
    model_name: str
    version: str

    model_config = ConfigDict(frozen=True)


class ModelDeactivated(BaseModel):
    """Event published when a model version is deactivated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ModelDeactivated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_id: str
    model_name: str
    version: str

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Thread-safe central registry for ML models.

    Manages registration, lookup, versioning, and lifecycle state.
    Advisory-only flag is enforced on every registered model.
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        versioning: Optional[ModelVersioning] = None,
        max_models: int = 500,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._versioning = versioning or ModelVersioning()
        # model_id -> ModelRecord (most recent record for that id)
        self._registry: Dict[str, ModelRecord] = {}
        # name -> set of model_ids (for name-based lookups)
        self._name_index: Dict[str, List[str]] = collections.defaultdict(list)
        self._max_models = max_models

    def register_model(
        self,
        name: str,
        model_type: str = "generic",
        version: Optional[SemanticVersion] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> ModelRecord:
        """Register a new ML model and return its immutable record."""
        with self._lock:
            if len(self._registry) >= self._max_models:
                raise RuntimeError(
                    f"ModelRegistry capacity exceeded: cannot register model '{name}' "
                    f"(limit={self._max_models})."
                )
            ver = version or SemanticVersion()
            record = ModelRecord(
                name=name,
                model_type=model_type,
                version=ver,
                description=description,
                tags=tags or [],
                hyperparameters=hyperparameters or {},
                status=ModelStatus.REGISTERED,
            )
            self._registry[record.model_id] = record
            self._name_index[name].append(record.model_id)
            self._versioning.register_version(record.model_id, ver)
            logger.info("Registered model '%s' (id=%s, v=%s)", name, record.model_id, ver)

            if self._event_bus:
                self._event_bus.publish(
                    ModelRegistered(
                        model_id=record.model_id,
                        model_name=name,
                        version=str(ver),
                    )
                )
            return record

    def unregister_model(self, model_id: str) -> bool:
        """Remove a model from the registry."""
        with self._lock:
            record = self._registry.pop(model_id, None)
            if record is None:
                return False
            ids = self._name_index.get(record.name, [])
            if model_id in ids:
                ids.remove(model_id)
            self._versioning.remove_model(model_id)
            logger.info("Unregistered model '%s' (id=%s)", record.name, model_id)
            return True

    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        """Retrieve a model record by its ID."""
        with self._lock:
            return self._registry.get(model_id)

    def list_models(
        self,
        status: Optional[ModelStatus] = None,
        name: Optional[str] = None,
    ) -> List[ModelRecord]:
        """List all registered models, optionally filtered by status or name."""
        with self._lock:
            records = list(self._registry.values())
            if status:
                records = [r for r in records if r.status == status]
            if name:
                records = [r for r in records if r.name == name]
            return records

    def update_status(self, model_id: str, status: ModelStatus) -> Optional[ModelRecord]:
        """Update model status, producing a new immutable record."""
        with self._lock:
            existing = self._registry.get(model_id)
            if not existing:
                return None
            updated = ModelRecord(
                model_id=existing.model_id,
                name=existing.name,
                version=existing.version,
                model_type=existing.model_type,
                description=existing.description,
                tags=existing.tags,
                hyperparameters=existing.hyperparameters,
                metrics=existing.metrics,
                created_at=existing.created_at,
                updated_at=datetime.now(timezone.utc),
                status=status,
            )
            self._registry[model_id] = updated

            if status == ModelStatus.ACTIVE and self._event_bus:
                self._versioning.set_active_version(model_id, updated.version)
                self._event_bus.publish(
                    ModelActivated(
                        model_id=model_id,
                        model_name=updated.name,
                        version=str(updated.version),
                    )
                )
            elif status == ModelStatus.INACTIVE and self._event_bus:
                self._event_bus.publish(
                    ModelDeactivated(
                        model_id=model_id,
                        model_name=updated.name,
                        version=str(updated.version),
                    )
                )
            return updated

    def get_by_name(self, name: str) -> List[ModelRecord]:
        """Get all model records matching a given name."""
        with self._lock:
            ids = self._name_index.get(name, [])
            return [self._registry[mid] for mid in ids if mid in self._registry]

    def count(self) -> int:
        """Return count of registered models."""
        with self._lock:
            return len(self._registry)

    def clear(self) -> None:
        """Clear all registry entries."""
        with self._lock:
            self._registry.clear()
            self._name_index.clear()
            self._versioning.clear()
