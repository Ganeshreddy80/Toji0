"""Thread-safe Model Manager — load, unload, activate, deactivate (Sprint 11A)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional, Set

from self_learning.model_registry import ModelRegistry
from self_learning.models.learning_models import ModelRecord, ModelStatus, SemanticVersion

logger = logging.getLogger(__name__)


class ModelManager:
    """Thread-safe ML model lifecycle manager.

    Enforces the constraint that only ONE version per model name may be
    active at any time. Advisory-only — no execution coupling.
    """

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self._lock = threading.RLock()
        self._registry = registry or ModelRegistry()
        # model_id -> loaded payload (simulated; in-memory marker)
        self._loaded: Set[str] = set()
        # model name -> active model_id (one active per name)
        self._active_by_name: Dict[str, str] = {}

    def load_model(self, model_id: str) -> Optional[ModelRecord]:
        """Mark a registered model as LOADED (simulates loading model artefact)."""
        with self._lock:
            record = self._registry.get_model(model_id)
            if record is None:
                logger.warning("load_model: model '%s' not found in registry", model_id)
                return None
            if record.status not in (ModelStatus.REGISTERED, ModelStatus.INACTIVE, ModelStatus.ERROR):
                logger.warning("load_model: model '%s' is in status '%s', skipping", model_id, record.status)
                return record

            self._loaded.add(model_id)
            updated = self._registry.update_status(model_id, ModelStatus.LOADED)
            logger.info("Loaded model '%s' (id=%s)", record.name, model_id)
            return updated

    def unload_model(self, model_id: str) -> Optional[ModelRecord]:
        """Unload a model, transitioning it to INACTIVE state."""
        with self._lock:
            record = self._registry.get_model(model_id)
            if record is None:
                return None

            self._loaded.discard(model_id)

            # Remove from active tracking if this was active
            active_id = self._active_by_name.get(record.name)
            if active_id == model_id:
                del self._active_by_name[record.name]

            updated = self._registry.update_status(model_id, ModelStatus.INACTIVE)
            logger.info("Unloaded model '%s' (id=%s)", record.name, model_id)
            return updated

    def activate_model(self, model_id: str) -> Optional[ModelRecord]:
        """Activate a loaded model. Deactivates any currently active version for that name."""
        with self._lock:
            record = self._registry.get_model(model_id)
            if record is None:
                logger.warning("activate_model: model '%s' not found", model_id)
                return None

            if model_id not in self._loaded and record.status != ModelStatus.LOADED:
                # Auto-load if registered but not yet loaded
                loaded = self.load_model(model_id)
                if loaded is None:
                    return None

            # Deactivate current active for this name
            current_active_id = self._active_by_name.get(record.name)
            if current_active_id and current_active_id != model_id:
                self._registry.update_status(current_active_id, ModelStatus.INACTIVE)
                logger.info("Deactivated previous active model id='%s'", current_active_id)

            self._active_by_name[record.name] = model_id
            updated = self._registry.update_status(model_id, ModelStatus.ACTIVE)
            logger.info("Activated model '%s' v%s (id=%s)", record.name, record.version, model_id)
            return updated

    def deactivate_model(self, model_id: str) -> Optional[ModelRecord]:
        """Deactivate an active model, transitioning it to INACTIVE."""
        with self._lock:
            record = self._registry.get_model(model_id)
            if record is None:
                return None

            active_id = self._active_by_name.get(record.name)
            if active_id == model_id:
                del self._active_by_name[record.name]

            updated = self._registry.update_status(model_id, ModelStatus.INACTIVE)
            logger.info("Deactivated model '%s' (id=%s)", record.name, model_id)
            return updated

    def get_active_model(self, name: str) -> Optional[ModelRecord]:
        """Get the currently active model for a given model name."""
        with self._lock:
            active_id = self._active_by_name.get(name)
            if not active_id:
                return None
            return self._registry.get_model(active_id)

    def is_loaded(self, model_id: str) -> bool:
        """Check if a model is loaded."""
        with self._lock:
            return model_id in self._loaded

    def is_active(self, model_id: str) -> bool:
        """Check if a model is the current active version."""
        with self._lock:
            record = self._registry.get_model(model_id)
            if not record:
                return False
            return self._active_by_name.get(record.name) == model_id

    @property
    def registry(self) -> ModelRegistry:
        """Expose the underlying model registry."""
        return self._registry

    def clear(self) -> None:
        """Reset manager state."""
        with self._lock:
            self._loaded.clear()
            self._active_by_name.clear()
            self._registry.clear()
