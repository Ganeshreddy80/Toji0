"""Thread-safe registry for managing feature definitions."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.feature_store.interfaces import IFeatureDefinition


class FeatureRegistry:
    """Registry containing all computed features definitions and versions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._definitions: dict[tuple[str, str], IFeatureDefinition] = {}

    def register(self, definition: IFeatureDefinition) -> None:
        """Register a feature definition."""
        key = (definition.name.upper(), definition.version)
        with self._lock:
            if key in self._definitions:
                raise ValueError(
                    f"Feature '{definition.name}' v{definition.version} is already registered"
                )
            self._definitions[key] = definition

    def get(self, name: str, version: str) -> IFeatureDefinition:
        """Retrieve a feature definition by name and version."""
        key = (name.upper(), version)
        with self._lock:
            if key not in self._definitions:
                raise KeyError(f"Feature '{name}' v{version} not found in registry")
            return self._definitions[key]

    def list_all(self) -> list[IFeatureDefinition]:
        """List all registered feature definitions."""
        with self._lock:
            return list(self._definitions.values())

    def clear(self) -> None:
        """Remove all registered feature definitions."""
        with self._lock:
            self._definitions.clear()
