"""Unit and integration tests for the TOJI Institutional Research Intelligence Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.research_intelligence.models import (
    ExperimentRecommendation,
    HypothesisStatus,
    ResearchHypothesis,
    ResearchRank,
    ResearchScore,
)
from research_platform.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
from research_platform.research_intelligence.scorer import ResearchScorer
from research_platform.research_intelligence.recommendation import RecommendationEngine
from research_platform.research_intelligence.ranking import ResearchRanker

# Integration components
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return ResearchIntelligenceOrchestrator(event_bus, container=container)


def test_research_scorer_math():
    """Verify research scoring points contributions logic."""
    scorer = ResearchScorer()

    # Highly successful: Sharpe=2.5, DD=5%, win_rate=65%, stability=80%
    # Sharpe points: 2.5 * 2.0 = 5.0
    # DD points: 2.0 - (0.05 * 10) = 1.5
    # Win rate points: 0.65 * 1.0 = 0.65
    # Stability points: 0.8 * 1.0 = 0.8
    # Sum: 5.0 + 1.5 + 0.65 + 0.8 = 7.95
    score = scorer.score_research("hyp-1", sharpe=2.5, drawdown=0.05, win_rate=0.65, stability=0.8)
    assert score.quality_score == pytest.approx(7.95)

    # Poor outcome: Sharpe=0.5, DD=25%, win_rate=40%, stability=40%
    # Sharpe points: 0.5 * 2.0 = 1.0
    # DD points: 2.0 - (0.25 * 10) = 0.0 (clamped)
    # Win rate points: 0.40 * 1.0 = 0.40
    # Stability points: 0.4 * 1.0 = 0.4
    # Sum: 1.0 + 0.0 + 0.4 + 0.4 = 1.8
    score_poor = scorer.score_research("hyp-2", sharpe=0.5, drawdown=0.25, win_rate=0.40, stability=0.40)
    assert score_poor.quality_score == pytest.approx(1.8)


def test_recommendation_logic():
    """Verify parameter adjustments recommendations based on score bounds."""
    engine = RecommendationEngine()

    hyp = ResearchHypothesis(
        hypothesis_id="hyp-1",
        description="test",
        symbol="BTCUSD",
        parameters={"lookback": 20}
    )

    # 1. High Drawdown -> Tighter stop loss recommended
    score_dd = ResearchScore(hypothesis_id="hyp-1", sharpe=1.2, drawdown=0.18, win_rate=0.55, parameter_stability=0.7, quality_score=4.5)
    rec_dd = engine.generate_recommendations(hyp, score_dd)
    assert rec_dd is not None
    assert rec_dd.actionable_parameter_changes["stop_loss"] == 0.02

    # 2. Low Sharpe -> Lookback window multiplier suggested
    score_low_sharpe = ResearchScore(hypothesis_id="hyp-1", sharpe=0.6, drawdown=0.05, win_rate=0.50, parameter_stability=0.6, quality_score=3.5)
    rec_sharpe = engine.generate_recommendations(hyp, score_low_sharpe)
    assert rec_sharpe is not None
    assert rec_sharpe.actionable_parameter_changes["lookback"] == 30  # 20 * 1.5


def test_hypothesis_ranking():
    """Verify topological sorting of hypotheses."""
    ranker = ResearchRanker()

    hyp1 = ResearchHypothesis(hypothesis_id="hyp-1", description="desc", symbol="BTCUSD")
    hyp2 = ResearchHypothesis(hypothesis_id="hyp-2", description="desc", symbol="BTCUSD")
    hyp3 = ResearchHypothesis(hypothesis_id="hyp-3", description="desc", symbol="BTCUSD")

    scores = {
        "hyp-1": ResearchScore(hypothesis_id="hyp-1", sharpe=1.5, drawdown=0.05, win_rate=0.55, parameter_stability=0.8, quality_score=6.0),
        "hyp-2": ResearchScore(hypothesis_id="hyp-2", sharpe=2.5, drawdown=0.04, win_rate=0.65, parameter_stability=0.9, quality_score=8.5),
        "hyp-3": ResearchScore(hypothesis_id="hyp-3", sharpe=0.5, drawdown=0.20, win_rate=0.45, parameter_stability=0.5, quality_score=2.0)
    }

    rank = ranker.rank_hypotheses([hyp1, hyp2, hyp3], scores)
    # Ranked: hyp-2 (8.5) -> hyp-1 (6.0) -> hyp-3 (2.0)
    assert rank.ranked_hypothesis_ids == ["hyp-2", "hyp-1", "hyp-3"]


def test_orchestrator_research_integration(orchestrator, container):
    """Verify orchestrator triggers memory logging, events, and knowledge graph links."""
    # 1. Register hypothesis
    hyp = orchestrator.register_hypothesis(
        hypothesis_id="hyp-alpha",
        description="momentum breakouts",
        symbol="BTCUSD",
        parameters={"lookback": 20}
    )
    assert hyp.status == HypothesisStatus.PENDING

    # 2. Score experiment
    score = orchestrator.score_experiment(
        hypothesis_id="hyp-alpha",
        sharpe=2.5,
        drawdown=0.05,
        win_rate=0.65,
        stability=0.8
    )
    
    # Validation checks
    assert score.quality_score >= 6.0
    updated_hyp = orchestrator.repository.get_hypothesis("hyp-alpha")
    assert updated_hyp.status == HypothesisStatus.VALIDATED

    # 3. Verify Memory logging
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("research_scores")
    assert len(mems) == 1
    assert mems[0].quality_score == score.quality_score

    # 4. Verify Knowledge Graph nodes and links
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "hyp-alpha" in node_ids
    assert "score-hyp-alpha" in node_ids

    # Check edges
    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "uses" in edge_types
    assert "references" in edge_types
