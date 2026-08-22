"""Ranks feature sets and model architectures based on performance metrics."""

from __future__ import annotations

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class FeatureAndModelRanker:
    """Sorts features and models according to empirical scoring attributes."""

    def rank_features(self, feature_scores: Dict[str, float]) -> List[str]:
        """Ranks feature keys descending by their significance/importance scores."""
        sorted_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)
        return [f[0] for f in sorted_features]

    def rank_models(self, model_metrics: Dict[str, Dict[str, float]], primary_metric: str = "sharpe") -> List[str]:
        """Ranks model names descending by their primary optimization metrics."""
        
        def get_metric(model_name: str) -> float:
            metrics = model_metrics.get(model_name, {})
            return metrics.get(primary_metric, 0.0)

        sorted_models = sorted(model_metrics.keys(), key=get_metric, reverse=True)
        return list(sorted_models)
