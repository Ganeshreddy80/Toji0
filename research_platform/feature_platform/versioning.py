"""Feature Version Manager implementation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.feature_platform.interfaces import IFeatureVersionManager
from research_platform.feature_platform.models import FeatureVersionInfo


class FeatureVersionManager(IFeatureVersionManager):
    """Tracks version history, code hashes, and Promotion statuses."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._versions: Dict[tuple[str, str], FeatureVersionInfo] = {}

    def create_version(self, info: FeatureVersionInfo) -> None:
        """Save a new feature version info record."""
        with self._lock:
            key = (info.feature_name, info.semantic_version)
            self._versions[key] = info

    def get_version(self, name: str, version: str) -> Optional[FeatureVersionInfo]:
        """Fetch version info."""
        with self._lock:
            return self._versions.get((name, version))

    def list_versions(self, name: str) -> List[FeatureVersionInfo]:
        """List all registered version records for a feature."""
        with self._lock:
            return [v for k, v in self._versions.items() if k[0] == name]
