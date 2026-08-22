"""Hypothesis ranker sorting engines implementing IResearchRanker.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, List
from research_platform.research_intelligence.interfaces import IResearchRanker
from research_platform.research_intelligence.models import ResearchHypothesis, ResearchRank, ResearchScore

logger = logging.getLogger(__name__)


class ResearchRanker(IResearchRanker):
    """Sorts active hypotheses based on cumulative research scores."""

    def rank_hypotheses(self, hypotheses: List[ResearchHypothesis], scores: Dict[str, ResearchScore]) -> ResearchRank:
        """Sort hypotheses descending by their score cards."""
        
        # Helper function to get the score card value, default to 0.0 if not scored
        def get_score_value(hyp: ResearchHypothesis) -> float:
            score = scores.get(hyp.hypothesis_id)
            return score.quality_score if score else 0.0

        # Sort descending
        sorted_hyps = sorted(hypotheses, key=get_score_value, reverse=True)
        ranked_ids = [h.hypothesis_id for h in sorted_hyps]

        rank = ResearchRank(
            ranking_id=f"rank-{uuid.uuid4().hex[:8]}",
            ranked_hypothesis_ids=ranked_ids
        )
        logger.info("Hypotheses ranked: %s", ranked_ids)
        return rank
