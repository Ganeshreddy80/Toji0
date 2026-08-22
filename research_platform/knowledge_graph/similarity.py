"""Similarity Engine comparing parameters features scores.
"""

from __future__ import annotations

import numpy as np
from typing import Dict

from research_platform.knowledge_graph.models import SimilarityResult


class SimilarityEngine:
    """Calculates cosine similarity distance metrics between nodes properties."""

    @staticmethod
    def calculate_similarity(
        node_a_id: str,
        properties_a: Dict[str, float],
        node_b_id: str,
        properties_b: Dict[str, float]
    ) -> SimilarityResult:
        """Calculate cosine similarity of numeric properties dict values."""
        keys = list(set(properties_a.keys()) & set(properties_b.keys()))
        if not keys:
            return SimilarityResult(source_node_id=node_a_id, match_node_id=node_b_id, similarity_score=0.0)

        vec_a = np.array([properties_a[k] for k in keys])
        vec_b = np.array([properties_b[k] for k in keys])

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0.0 or norm_b == 0.0:
            score = 0.0
        else:
            score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

        return SimilarityResult(
            source_node_id=node_a_id,
            match_node_id=node_b_id,
            similarity_score=score
        )
