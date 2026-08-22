"""Feature importance engine for the Research Platform (Sprint 6)."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List

from research_platform.core.interfaces import IFeatureImportanceEngine
from research_platform.core.models import FeatureImportance, FeatureImportanceResult


class FeatureImportanceEngine(IFeatureImportanceEngine):
    """Computes deterministic feature attribution scores and rankings."""

    def calculate_importance(
        self,
        experiment_id: str,
        feature_matrix: List[Dict[str, float]],
        target_returns: List[float],
        method: str = "PERMUTATION",
    ) -> FeatureImportanceResult:
        """Compute feature importance rankings from feature dictionary series and returns."""
        if not feature_matrix or not target_returns:
            return FeatureImportanceResult(
                experiment_id=experiment_id,
                method=method,
                features=[],
                evaluated_at=datetime.now(timezone.utc),
            )

        feature_names = list(feature_matrix[0].keys())
        n = min(len(feature_matrix), len(target_returns))

        if n <= 1 or not feature_names:
            return FeatureImportanceResult(
                experiment_id=experiment_id,
                method=method,
                features=[],
                evaluated_at=datetime.now(timezone.utc),
            )

        mean_y = sum(target_returns[:n]) / n
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in target_returns[:n]) / n)

        feature_scores: List[tuple[str, float]] = []

        for name in feature_names:
            x_vals = [feature_matrix[i].get(name, 0.0) for i in range(n)]
            mean_x = sum(x_vals) / n
            std_x = math.sqrt(sum((x - mean_x) ** 2 for x in x_vals) / n)

            if std_x > 0.0 and std_y > 0.0:
                cov = sum((x_vals[i] - mean_x) * (target_returns[i] - mean_y) for i in range(n)) / n
                corr = abs(cov / (std_x * std_y))
            else:
                corr = 0.0

            feature_scores.append((name, round(corr, 4)))

        # Sort descending by importance score
        feature_scores.sort(key=lambda item: item[1], reverse=True)

        features: List[FeatureImportance] = []
        for rank, (name, score) in enumerate(feature_scores, start=1):
            features.append(
                FeatureImportance(
                    feature_name=name,
                    importance_score=score,
                    rank=rank,
                    method=method,
                )
            )

        return FeatureImportanceResult(
            experiment_id=experiment_id,
            method=method,
            features=features,
            evaluated_at=datetime.now(timezone.utc),
        )
