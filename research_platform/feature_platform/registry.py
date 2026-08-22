"""Feature Registry implementation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.feature_platform.interfaces import IFeatureRegistry
from research_platform.feature_platform.models import FeatureRecord


class FeatureRegistry(IFeatureRegistry):
    """Memory-backed, thread-safe Feature Registry implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry: Dict[str, FeatureRecord] = {}

    def register(self, record: FeatureRecord) -> None:
        """Register a feature in the metadata store.

        Raises:
            ValueError: If the feature name is empty or already exists,
                        or dependencies are missing.
        """
        if not record.name:
            raise ValueError("Feature name cannot be empty.")

        with self._lock:
            if record.name in self._registry:
                raise ValueError(f"Feature '{record.name}' is already registered.")

            # Validate that dependencies exist
            for dep in record.dependencies:
                if dep not in self._registry:
                    raise ValueError(
                        f"Cannot register '{record.name}': dependency '{dep}' is missing from the registry."
                    )

            self._registry[record.name] = record

    def get(self, name: str) -> Optional[FeatureRecord]:
        """Fetch feature details by unique technical name."""
        with self._lock:
            return self._registry.get(name)

    def list_all(self) -> List[FeatureRecord]:
        """Return all registered features."""
        with self._lock:
            return list(self._registry.values())
