"""Research intelligence orchestrator coordinating hypotheses tracking, scorecard, recommendations, and rankings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.research_intelligence.interfaces import IResearchIntelligenceOrchestrator
from research_platform.research_intelligence.models import (
    ExperimentRecommendation,
    HypothesisStatus,
    ResearchHypothesis,
    ResearchRank,
    ResearchScore,
)
from research_platform.research_intelligence.repository import ResearchIntelligenceRepository
from research_platform.research_intelligence.scorer import ResearchScorer
from research_platform.research_intelligence.recommendation import RecommendationEngine
from research_platform.research_intelligence.ranking import ResearchRanker
from research_platform.research_intelligence.events import (
    ExperimentFailed,
    ExperimentSucceeded,
    HypothesisRegistered,
    RecommendationGenerated,
    ResearchRanked,
    ResearchScored,
)

logger = logging.getLogger(__name__)


class ResearchIntelligenceOrchestrator(IResearchIntelligenceOrchestrator):
    """Central orchestrator managing decision-support scoring pipelines and ranking maps."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = ResearchIntelligenceRepository()

        # Engines
        self._scorer = ResearchScorer()
        self._recommendation_engine = RecommendationEngine()
        self._ranker = ResearchRanker()

    @property
    def repository(self) -> ResearchIntelligenceRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, hypothesis: ResearchHypothesis, score: Optional[ResearchScore] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Hypothesis Node
            kg_orch.register_node(
                node_id=hypothesis.hypothesis_id,
                node_type="HYPOTHESIS",
                subsystem="research_intelligence",
                event="HypothesisRegistered",
                author="system",
                properties={"status": hypothesis.status.value, "symbol": hypothesis.symbol}
            )

            # Link symbol asset
            kg_orch.register_node(
                node_id=hypothesis.symbol,
                node_type="ASSET",
                subsystem="research_intelligence",
                event="HypothesisRegistered",
                author="system",
                properties={"symbol": hypothesis.symbol}
            )
            kg_orch.link_nodes(
                source_id=hypothesis.hypothesis_id,
                target_id=hypothesis.symbol,
                relationship_type="uses",
                subsystem="research_intelligence"
            )

            if score:
                score_node_id = f"score-{score.hypothesis_id}"
                kg_orch.register_node(
                    node_id=score_node_id,
                    node_type="RESEARCH_SCORE",
                    subsystem="research_intelligence",
                    event="ResearchScored",
                    author="system",
                    properties={"quality_score": score.quality_score}
                )
                kg_orch.link_nodes(
                    source_id=score_node_id,
                    target_id=hypothesis.hypothesis_id,
                    relationship_type="references",
                    subsystem="research_intelligence"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def register_hypothesis(
        self,
        hypothesis_id: str,
        description: str,
        symbol: str,
        parameters: Dict[str, Any]
    ) -> ResearchHypothesis:
        """Register a new research hypothesis and track dependencies."""
        hyp = ResearchHypothesis(
            hypothesis_id=hypothesis_id,
            description=description,
            symbol=symbol,
            parameters=parameters,
            status=HypothesisStatus.PENDING
        )
        self._repo.save_hypothesis(hyp)
        self._event_bus.publish(HypothesisRegistered(payload={"hypothesis_id": hypothesis_id}))

        # Downstream
        self._publish_memory_record("research_hypotheses", hyp)
        self._update_knowledge_graph(hyp)

        return hyp

    def score_experiment(
        self,
        hypothesis_id: str,
        sharpe: float,
        drawdown: float,
        win_rate: float,
        stability: float
    ) -> ResearchScore:
        """Grades completed experiments, saves score card, evaluates recommendations and updates status."""
        hyp = self._repo.get_hypothesis(hypothesis_id)
        if not hyp:
            raise ValueError(f"Hypothesis '{hypothesis_id}' not found.")

        # 1. Compute score
        score = self._scorer.score_research(hypothesis_id, sharpe, drawdown, win_rate, stability)
        self._repo.save_score(score)
        self._event_bus.publish(ResearchScored(payload={"hypothesis_id": hypothesis_id, "score": score.quality_score}))

        # 2. Status shift validation
        validated = score.quality_score >= 6.0
        new_status = HypothesisStatus.VALIDATED if validated else HypothesisStatus.REJECTED
        
        updated_hyp = hyp.model_copy(update={"status": new_status})
        self._repo.save_hypothesis(updated_hyp)

        if validated:
            self._event_bus.publish(ExperimentSucceeded(payload={"hypothesis_id": hypothesis_id}))
        else:
            self._event_bus.publish(ExperimentFailed(payload={"hypothesis_id": hypothesis_id}))

        # 3. Generate parameter corrections
        rec = self._recommendation_engine.generate_recommendations(updated_hyp, score)
        if rec:
            self._repo.save_recommendation(rec)
            self._event_bus.publish(RecommendationGenerated(payload={"recommendation_id": rec.recommendation_id}))
            self._publish_memory_record("research_recommendations", rec)

        # Downstream
        self._publish_memory_record("research_scores", score)
        self._update_knowledge_graph(updated_hyp, score)

        return score

    def recompute_rankings(self) -> ResearchRank:
        """Rank all active hypotheses descending by score."""
        hyps = self._repo.list_hypotheses()
        
        # Pull all score cards
        scores = {}
        for h in hyps:
            sc = self._repo.get_score(h.hypothesis_id)
            if sc:
                scores[h.hypothesis_id] = sc

        rank = self._ranker.rank_hypotheses(hyps, scores)
        self._repo.save_rank(rank)
        self._event_bus.publish(ResearchRanked(payload={"ranked_ids": rank.ranked_hypothesis_ids}))

        # Sync down to memory
        self._publish_memory_record("research_rankings", rank)

        return rank
