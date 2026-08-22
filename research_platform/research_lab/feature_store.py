"""Feature store engine extracting pricing features.
"""

from __future__ import annotations

from typing import List
from research_platform.research_lab.interfaces import IFeatureStore
from research_platform.research_lab.models import FeatureData


class FeatureStore(IFeatureStore):
    """Calculates feature values like diff differences from raw prices."""

    def extract_features(self, name: str, data: List[float]) -> FeatureData:
        # Extract features (e.g. logarithmic differences)
        values = []
        if len(data) > 1:
            for idx in range(1, len(data)):
                diff = data[idx] - data[idx - 1]
                values.append(diff)

        return FeatureData(
            feature_id=name,
            values=values
        )
