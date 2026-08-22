"""Thread-safe, append-only repository for storing research hypotheses, scores, and rankings.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.research_intelligence.interfaces import IResearchIntelligenceRepository
from research_platform.research_intelligence.models import (
    ExperimentRecommendation,
    ResearchHypothesis,
    ResearchRank,
    ResearchScore,
)


class ResearchIntelligenceRepository(IResearchIntelligenceRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hypotheses: Dict[str, ResearchHypothesis] = {}
        self._scores: Dict[str, ResearchScore] = {}
        self._recommendations: Dict[str, List[ExperimentRecommendation]] = {}
        self._ranks: List[ResearchRank] = []

    def save_hypothesis(self, hypothesis: ResearchHypothesis) -> None:
        with self._lock:
            self._hypotheses[hypothesis.hypothesis_id] = hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ResearchHypothesis]:
        with self._lock:
            return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(self) -> List[ResearchHypothesis]:
        with self._lock:
            return list(self._hypotheses.values())

    def save_score(self, score: ResearchScore) -> None:
        with self._lock:
            self._scores[score.hypothesis_id] = score

    def get_score(self, hypothesis_id: str) -> Optional[ResearchScore]:
        with self._lock:
            return self._scores.get(hypothesis_id)

    def save_recommendation(self, recommendation: ExperimentRecommendation) -> None:
        with self._lock:
            hyp_id = recommendation.hypothesis_id
            if hyp_id not in self._recommendations:
                self._recommendations[hyp_id] = []
            self._recommendations[hyp_id].append(recommendation)

    def list_recommendations(self, hypothesis_id: str) -> List[ExperimentRecommendation]:
        with self._lock:
            return list(self._recommendations.get(hypothesis_id, []))

    def save_rank(self, rank: ResearchRank) -> None:
        with self._lock:
            self._ranks.append(rank)

    def get_latest_rank(self) -> Optional[ResearchRank]:
        with self._lock:
            if not self._ranks:
                return None
            return self._ranks[-1]
