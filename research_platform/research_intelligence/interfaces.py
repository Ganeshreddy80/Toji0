"""Abstract contracts for the Research Intelligence Engine.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from research_platform.research_intelligence.models import (
    ExperimentRecommendation,
    ResearchHypothesis,
    ResearchRank,
    ResearchScore,
)


class IResearchIntelligenceRepository(abc.ABC):
    """Abstract contract for persisting and retrieving research experiments and recommendations."""

    @abc.abstractmethod
    def save_hypothesis(self, hypothesis: ResearchHypothesis) -> None:
        """Persist a hypothesis."""

    @abc.abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Optional[ResearchHypothesis]:
        """Retrieve a hypothesis by ID."""

    @abc.abstractmethod
    def list_hypotheses(self) -> List[ResearchHypothesis]:
        """List all hypotheses."""

    @abc.abstractmethod
    def save_score(self, score: ResearchScore) -> None:
        """Persist a research scoring profile."""

    @abc.abstractmethod
    def get_score(self, hypothesis_id: str) -> Optional[ResearchScore]:
        """Retrieve the score card for a hypothesis."""

    @abc.abstractmethod
    def save_recommendation(self, recommendation: ExperimentRecommendation) -> None:
        """Persist an advisory parameter recommendation."""

    @abc.abstractmethod
    def list_recommendations(self, hypothesis_id: str) -> List[ExperimentRecommendation]:
        """List recommendations for a hypothesis."""

    @abc.abstractmethod
    def save_rank(self, rank: ResearchRank) -> None:
        """Persist a hypothesis ranking list."""

    @abc.abstractmethod
    def get_latest_rank(self) -> Optional[ResearchRank]:
        """Retrieve the latest ranking results."""


class IResearchScorer(abc.ABC):
    """Abstract contract for scoring research results."""

    @abc.abstractmethod
    def score_research(self, hypothesis_id: str, sharpe: float, drawdown: float, win_rate: float, stability: float) -> ResearchScore:
        """Calculate quality scorecard profile."""


class IRecommendationEngine(abc.ABC):
    """Abstract contract for generating advisory recommendations."""

    @abc.abstractmethod
    def generate_recommendations(self, hypothesis: ResearchHypothesis, score: ResearchScore) -> Optional[ExperimentRecommendation]:
        """Construct advisory parameter corrections recommendations."""


class IResearchRanker(abc.ABC):
    """Abstract contract for sorting and ranking hypotheses."""

    @abc.abstractmethod
    def rank_hypotheses(self, hypotheses: List[ResearchHypothesis], scores: Dict[str, ResearchScore]) -> ResearchRank:
        """Sort hypotheses based on research scores quality."""


class IResearchIntelligenceOrchestrator(abc.ABC):
    """Abstract contract for the research intelligence orchestrator."""
    pass
