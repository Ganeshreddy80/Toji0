"""Feature Catalog implementation.
"""

from __future__ import annotations

import threading
from typing import List, Optional

from research_platform.feature_platform.interfaces import IFeatureCatalog
from research_platform.feature_platform.models import FeatureRecord


class FeatureCatalog(IFeatureCatalog):
    """Searchable catalog index mapping categories, tags, and assets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._features: List[FeatureRecord] = []

    def register_feature(self, record: FeatureRecord) -> None:
        """Register a feature in the local catalog indexing list."""
        with self._lock:
            # check duplicate and remove first if it exists
            self._features = [f for f in self._features if f.name != record.name]
            self._features.append(record)

    def search(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[FeatureRecord]:
        """Filter registered features by category or tag filters."""
        with self._lock:
            results = self._features
            if category:
                results = [f for f in results if f.category.upper() == category.upper()]
            if tags:
                tag_set = set(t.lower() for t in tags)
                results = [f for f in results if tag_set.intersection(t.lower() for t in f.tags)]
            return results
