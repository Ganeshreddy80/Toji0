"""Unit and integration tests for the TOJI Institutional Multi-Agent Decision System.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.multi_agent.models import (
    AgentConsensus,
    AgentProposal,
    AgentRequest,
    AgentType,
)
from research_platform.multi_agent.orchestrator import MultiAgentOrchestrator
from research_platform.multi_agent.consensus import AgentConsensusEngine
from research_platform.multi_agent.agents import RiskAgent, MarketAgent, ResearchAgent

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
    return MultiAgentOrchestrator(event_bus, container=container)


def test_agent_proposal_evaluation():
    """Verify that agents generate correct proposals based on target context variables."""
    risk_agent = RiskAgent()
    market_agent = MarketAgent()

    # Context A: Drawdown exceeds threshold -> RiskAgent proposes tight stop loss
    req_risk = AgentRequest(session_id="s1", strategy_id="strat-1", parameters={}, context={"drawdown": 0.12})
    prop_risk = risk_agent.evaluate_proposal(req_risk, [])
    assert prop_risk.agent_type == AgentType.RISK
    assert prop_risk.advisory_recommendations["stop_loss"] == 0.02

    # Context B: Market is high volatility -> MarketAgent proposes volume scaling
    req_market = AgentRequest(session_id="s2", strategy_id="strat-1", parameters={}, context={"regime": "HIGH_VOLATILITY"})
    prop_market = market_agent.evaluate_proposal(req_market, [])
    assert prop_market.agent_type == AgentType.MARKET
    assert prop_market.advisory_recommendations["volume_scale"] == 0.5


def test_consensus_precedence_rules():
    """Verify conflict resolution precedence maps (e.g. RISK has highest priority)."""
    engine = AgentConsensusEngine()

    p_risk = AgentProposal(
        agent_type=AgentType.RISK,
        confidence_score=0.9,
        advisory_recommendations={"stop_loss": 0.02},
        rationale="Risk says tight stops"
    )

    p_research = AgentProposal(
        agent_type=AgentType.RESEARCH,
        confidence_score=0.8,
        advisory_recommendations={"stop_loss": 0.05, "lookback": 25},
        rationale="Research says wide stops"
    )

    consensus = engine.compile_consensus("sess-1", [p_risk, p_research])
    
    # 1. RISK stop_loss (0.02) overrides RESEARCH stop_loss (0.05)
    assert consensus.final_recommendation["stop_loss"] == 0.02
    
    # 2. Non-conflicting parameters (lookback) are merged in
    assert consensus.final_recommendation["lookback"] == 25


def test_orchestrator_multi_agent_session_run(orchestrator, container):
    """Verify orchestrator runs all agents, registers memory logs, and links graphs."""
    consensus = orchestrator.execute_session(
        strategy_id="strat-alpha",
        parameters={"lookback": 8},  # Will trigger ResearchAgent suggestion to increase lookback
        context={"drawdown": 0.12, "regime": "HIGH_VOLATILITY"}  # Will trigger Risk and Market suggestions
    )

    # Check consolidated recommendations
    assert consensus.final_recommendation["lookback"] == 15
    assert consensus.final_recommendation["volume_scale"] == 0.5
    assert consensus.final_recommendation["stop_loss"] == 0.02
    
    # Risk agent triggered halt limit parameter -> consensus status becomes REJECTED
    assert consensus.status == "REJECTED"

    # 1. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("agent_consensus")
    assert len(mems) == 1
    assert mems[0].session_id == consensus.session_id

    # 2. Verify Knowledge Graph
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert consensus.session_id in node_ids
    assert f"consensus-{consensus.session_id}" in node_ids

    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "references" in edge_types
