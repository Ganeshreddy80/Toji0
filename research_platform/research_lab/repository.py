"""Thread-safe memory repository caching features, factors, hypotheses.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.research_lab.interfaces import IResearchLabRepository
from research_platform.research_lab.models import FeatureData, AlphaFactor, Hypothesis


class ResearchLabRepository(IResearchLabRepository):
    """Memory-backed, thread-safe repository for research lab configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._features: Dict[str, FeatureData] = {}
        self._factors: Dict[str, AlphaFactor] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}

    def save_feature(self, feature: FeatureData) -> None:
        with self._lock:
            self._features[feature.feature_id] = feature

    def get_feature(self, feature_id: str) -> Optional[FeatureData]:
        with self._lock:
            return self._features.get(feature_id)

    def save_factor(self, factor: AlphaFactor) -> None:
        with self._lock:
            self._factors[factor.factor_id] = factor

    def get_factor(self, factor_id: str) -> Optional[AlphaFactor]:
        with self._lock:
            return self._factors.get(factor_id)

    def save_hypothesis(self, hypo: Hypothesis) -> None:
        with self._lock:
            self._hypotheses[hypo.hypothesis_id] = hypo

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        with self._lock:
            return self._hypotheses.get(hypothesis_id)
