"""Unit tests for the TOJI Institutional Knowledge Graph Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.knowledge_graph.models import KnowledgeEdge, KnowledgeNode
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.knowledge_graph.node import NodeEngine
from research_platform.knowledge_graph.similarity import SimilarityEngine


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return KnowledgeGraphOrchestrator(event_bus)


def test_node_edge_registration_and_versioning(orchestrator):
    """Verify node and edge saving with metadata."""
    # 1. Register Node
    node = orchestrator.register_node(
        node_id="strat-atr",
        node_type="STRATEGY",
        subsystem="strategy_lab",
        event="StrategyCreated",
        author="system",
        properties={"ATR": 14}
    )
    assert node.version == 1
    assert node.node_type == "STRATEGY"

    # Version increment check
    updated = NodeEngine.increment_version(node, {"ATR": 15})
    orchestrator.repository.save_node(updated)
    
    current = orchestrator.repository.list_nodes()
    assert len(current) == 1
    assert current[0].version == 2
    assert current[0].properties["ATR"] == 15


def test_relationship_integrity_and_validation(orchestrator):
    """Verify relationship type constraint checks block invalid links."""
    n_strat = orchestrator.register_node(
        node_id="strat-1", node_type="STRATEGY", subsystem="strategy_lab", event="s", author="s"
    )
    n_ind = orchestrator.register_node(
        node_id="ind-1", node_type="INDICATOR", subsystem="feature_store", event="s", author="s"
    )

    # valid link
    edge1 = orchestrator.link_nodes("strat-1", "ind-1", "uses", subsystem="strategy_lab")
    assert edge1 is not None

    # invalid link: human approval executed_by trade
    n_app = orchestrator.register_node(
        node_id="app-1", node_type="HUMAN_APPROVAL", subsystem="gov", event="s", author="s"
    )
    edge2 = orchestrator.link_nodes("app-1", "ind-1", "executed_by", subsystem="gov")
    assert edge2 is None


def test_graph_multi_hop_traversals(orchestrator):
    """Verify BFS traversal paths query."""
    n1 = orchestrator.register_node("A", "STRATEGY", "s", "e", "a")
    n2 = orchestrator.register_node("B", "INDICATOR", "s", "e", "a")
    n3 = orchestrator.register_node("C", "DATASET", "s", "e", "a")

    orchestrator.link_nodes("A", "B", "uses", "s")
    orchestrator.link_nodes("B", "C", "derived_from", "s")

    res = orchestrator.traverse_graph_path("A", "C")
    assert res.visited_node_ids == ["A", "B", "C"]
    assert len(res.edges_traversed) == 2


def test_cycle_detection_and_dependencies(orchestrator):
    """Verify topological sorting and cyclic dependency checks."""
    n1 = orchestrator.register_node("A", "STRATEGY", "s", "e", "a")
    n2 = orchestrator.register_node("B", "INDICATOR", "s", "e", "a")

    # A depends on B
    orchestrator.link_nodes("A", "B", "depends_on", "s")
    res1 = orchestrator.resolve_dependencies()
    assert res1.cycles_detected is False
    assert res1.ordered_node_ids == ["B", "A"]  # B compiles first

    # Introduce cycle: B depends on A
    orchestrator.link_nodes("B", "A", "depends_on", "s")
    res2 = orchestrator.resolve_dependencies()
    assert res2.cycles_detected is True


def test_regime_similarity_matching():
    """Verify regimes cosine similarity score calculations."""
    props_a = {"volatility": 0.2, "trend": 0.8}
    props_b = {"volatility": 0.22, "trend": 0.78}

    res = SimilarityEngine.calculate_similarity("node-a", props_a, "node-b", props_b)
    assert res.similarity_score > 0.95


def test_drawdown_causality_analysis(orchestrator):
    """Verify drawdown root cause traces failed_due_to relations."""
    n_pnl = orchestrator.register_node("pnl-drawdown", "PNL", "s", "e", "a")
    n_err = orchestrator.register_node("obs-error", "OBSERVABILITY_EVENT", "s", "e", "a")

    orchestrator.link_nodes("pnl-drawdown", "obs-error", "failed_due_to", "s")

    res = orchestrator.analyze_drawdown_cause("pnl-drawdown")
    assert res.culprit_node_id == "obs-error"
    assert "caused by failure" in res.explanation


def test_lineage_dataset_origins(orchestrator):
    """Verify dataset derived_from origins tracking."""
    n_feat = orchestrator.register_node("feature-1", "FEATURE", "s", "e", "a")
    n_ds = orchestrator.register_node("dataset-1", "DATASET", "s", "e", "a")

    orchestrator.link_nodes("feature-1", "dataset-1", "derived_from", "s")

    res = orchestrator.trace_lineage("feature-1")
    assert "dataset-1" in res.source_ids


def test_chronological_timeline_sorting(orchestrator):
    """Verify nodes sort chronologically by timestamp."""
    ts_now = datetime.now(timezone.utc)
    
    n_past = orchestrator.register_node("old-node", "STRATEGY", "s", "e", "a")
    n_past = n_past.model_copy(update={"created_at": ts_now - timedelta(seconds=10)})
    orchestrator.repository.save_node(n_past)

    n_new = orchestrator.register_node("new-node", "TRADE", "s", "e", "a")
    
    timeline = orchestrator.compile_chronological_timeline()
    assert len(timeline) == 2
    assert timeline[0].event_name == "STRATEGY_REGISTERED"
    assert timeline[1].event_name == "TRADE_REGISTERED"


def test_visual_mermaid_rendering(orchestrator):
    """Verify visual schema render formats as flow diagram string."""
    orchestrator.register_node("A", "STRATEGY", "s", "e", "a")
    orchestrator.register_node("B", "INDICATOR", "s", "e", "a")
    orchestrator.link_nodes("A", "B", "uses", "s")

    mermaid = orchestrator.get_visual_schema()
    assert "graph TD" in mermaid
    assert "A -->|uses| B" in mermaid
