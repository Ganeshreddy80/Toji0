"""Multi-objective optimization and Pareto-front ranking for alpha signals.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List

from research_platform.alpha_factory.models import AlphaMetrics, AlphaRanking


class AlphaOptimizer:
    """Ranks alpha candidates using multi-objective metrics (power, stability, complexity, turnover)."""

    @staticmethod
    def rank_candidates(candidates_metrics: Dict[str, AlphaMetrics]) -> List[AlphaRanking]:
        """Rank candidates using a weighted ranking sum of multiple objectives.

        Objectives:
            - rank_ic (maximize)
            - stability (maximize)
            - complexity (minimize)
            - turnover (minimize)
            - capacity (maximize)
        """
        if not candidates_metrics:
            return []

        ids = list(candidates_metrics.keys())
        n = len(ids)

        # Extracted metrics arrays
        rank_ic = np.array([abs(candidates_metrics[cid].rank_ic) for cid in ids])
        stability = np.array([candidates_metrics[cid].ic_stability for cid in ids])
        complexity = np.array([candidates_metrics[cid].complexity for cid in ids])
        turnover = np.array([candidates_metrics[cid].turnover for cid in ids])
        capacity = np.array([candidates_metrics[cid].capacity for cid in ids])

        # Get ranks for each objective (0 to n-1 where n-1 is best)
        rank_ic_ranks = np.argsort(np.argsort(rank_ic))
        stability_ranks = np.argsort(np.argsort(stability))
        complexity_ranks = np.argsort(np.argsort(-complexity))  # lower complexity is better
        turnover_ranks = np.argsort(np.argsort(-turnover))      # lower turnover is better
        capacity_ranks = np.argsort(np.argsort(capacity))

        # Composite score: sum of normalized ranks
        scores = []
        for i in range(n):
            score = (
                0.3 * (rank_ic_ranks[i] / (n + 1e-10)) +
                0.2 * (stability_ranks[i] / (n + 1e-10)) +
                0.2 * (complexity_ranks[i] / (n + 1e-10)) +
                0.15 * (turnover_ranks[i] / (n + 1e-10)) +
                0.15 * (capacity_ranks[i] / (n + 1e-10))
            )
            scores.append(float(score * 100.0))  # Scale to 0-100

        # Sort candidate IDs by score descending
        sorted_indices = np.argsort(-np.array(scores))

        rankings = []
        for rank_pos, idx in enumerate(sorted_indices):
            cid = ids[idx]
            rankings.append(
                AlphaRanking(
                    candidate_id=cid,
                    score=scores[idx],
                    rank_position=rank_pos + 1,
                    metrics_scores={
                        "rank_ic_rank": float(rank_ic_ranks[idx]),
                        "stability_rank": float(stability_ranks[idx]),
                        "complexity_rank": float(complexity_ranks[idx])
                    }
                )
            )

        return rankings
