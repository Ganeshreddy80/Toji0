"""Thread-safe Semantic Version Manager for the Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

import collections
import logging
import threading
from typing import Dict, List, Optional

from self_learning.models.learning_models import ModelRecord, SemanticVersion

logger = logging.getLogger(__name__)


class VersionHistory:
    """Bounded ordered version history for a single model."""

    def __init__(self, max_versions: int = 50) -> None:
        self._versions: collections.deque[SemanticVersion] = collections.deque(maxlen=max_versions)
        self._active: Optional[SemanticVersion] = None
        self._rollback_target: Optional[SemanticVersion] = None

    def add_version(self, version: SemanticVersion) -> None:
        self._versions.append(version)

    def set_active(self, version: SemanticVersion) -> None:
        # Previous active becomes rollback target
        if self._active and self._active != version:
            self._rollback_target = self._active
        self._active = version

    @property
    def active(self) -> Optional[SemanticVersion]:
        return self._active

    @property
    def rollback_target(self) -> Optional[SemanticVersion]:
        return self._rollback_target

    def get_history(self) -> List[SemanticVersion]:
        return list(self._versions)

    def has_version(self, version: SemanticVersion) -> bool:
        return version in self._versions


class ModelVersioning:
    """Thread-safe semantic version manager tracking model version history,
    active version, and rollback targets across all registered models.
    """

    def __init__(self, max_versions_per_model: int = 50) -> None:
        self._lock = threading.RLock()
        self._max_versions = max_versions_per_model
        self._histories: Dict[str, VersionHistory] = {}

    def register_version(self, model_id: str, version: SemanticVersion) -> None:
        """Register a new version for a model."""
        with self._lock:
            if model_id not in self._histories:
                self._histories[model_id] = VersionHistory(self._max_versions)
            self._histories[model_id].add_version(version)
            logger.info("Registered version %s for model '%s'", version, model_id)

    def set_active_version(self, model_id: str, version: SemanticVersion) -> bool:
        """Set the active version for a model. Previous active becomes rollback target."""
        with self._lock:
            if model_id not in self._histories:
                return False
            hist = self._histories[model_id]
            if not hist.has_version(version):
                return False
            hist.set_active(version)
            logger.info("Set active version %s for model '%s'", version, model_id)
            return True

    def get_active_version(self, model_id: str) -> Optional[SemanticVersion]:
        """Get the currently active version for a model."""
        with self._lock:
            hist = self._histories.get(model_id)
            return hist.active if hist else None

    def get_rollback_target(self, model_id: str) -> Optional[SemanticVersion]:
        """Get the rollback target version (previous active) for a model."""
        with self._lock:
            hist = self._histories.get(model_id)
            return hist.rollback_target if hist else None

    def rollback(self, model_id: str) -> Optional[SemanticVersion]:
        """Rollback to the previous active version. Returns the restored version or None."""
        with self._lock:
            hist = self._histories.get(model_id)
            if not hist or not hist.rollback_target:
                return None
            target = hist.rollback_target
            hist.set_active(target)
            logger.info("Rolled back model '%s' to version %s", model_id, target)
            return target

    def get_version_history(self, model_id: str) -> List[SemanticVersion]:
        """Get ordered version history list for a model."""
        with self._lock:
            hist = self._histories.get(model_id)
            return hist.get_history() if hist else []

    def next_patch(self, model_id: str) -> SemanticVersion:
        """Compute the next patch version for a model based on its active version."""
        with self._lock:
            hist = self._histories.get(model_id)
            if hist and hist.active:
                return hist.active.bump_patch()
            return SemanticVersion(major=0, minor=1, patch=0)

    def remove_model(self, model_id: str) -> bool:
        """Remove all version history for a model."""
        with self._lock:
            if model_id in self._histories:
                del self._histories[model_id]
                return True
            return False

    def clear(self) -> None:
        """Clear all version histories."""
        with self._lock:
            self._histories.clear()
