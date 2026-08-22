"""Multi-agent orchestrator managing collaborative sessions and compiling consensus recommendations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.multi_agent.interfaces import IMultiAgentOrchestrator
from research_platform.multi_agent.models import (
    AgentConsensus,
    AgentProposal,
    AgentRequest,
    AgentType,
)
from research_platform.multi_agent.repository import AgentRepository
from research_platform.multi_agent.consensus import AgentConsensusEngine
from research_platform.multi_agent.agents import (
    AIReviewerAgent,
    ExecutionAgent,
    KGAgent,
    MarketAgent,
    MemoryAgent,
    PortfolioAgent,
    ResearchAgent,
    RiskAgent,
)
from research_platform.multi_agent.events import (
    AgentConsensusReached,
    AgentProposalSubmitted,
    AgentSessionStarted,
)

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator(IMultiAgentOrchestrator):
    """Central coordinator for orchestrating collaborative agent sessions."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = AgentRepository()

        # Engines
        self._consensus_engine = AgentConsensusEngine()

        # Instantiate agents
        self._agents = {
            AgentType.RESEARCH: ResearchAgent(),
            AgentType.MARKET: MarketAgent(),
            AgentType.PORTFOLIO: PortfolioAgent(),
            AgentType.RISK: RiskAgent(),
            AgentType.EXECUTION: ExecutionAgent(),
            AgentType.MEMORY: MemoryAgent(),
            AgentType.KG: KGAgent(),
            AgentType.AI_REVIEWER: AIReviewerAgent()
        }

    @property
    def repository(self) -> AgentRepository:
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

    def _update_knowledge_graph(self, request: AgentRequest, consensus: Optional[AgentConsensus] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Session Node
            kg_orch.register_node(
                node_id=request.session_id,
                node_type="AGENT_SESSION",
                subsystem="multi_agent",
                event="AgentSessionStarted",
                author="system",
                properties={"strategy_id": request.strategy_id}
            )

            # Link Strategy
            kg_orch.register_node(
                node_id=request.strategy_id,
                node_type="STRATEGY",
                subsystem="multi_agent",
                event="AgentSessionStarted",
                author="system",
                properties={"strategy_id": request.strategy_id}
            )
            kg_orch.link_nodes(
                source_id=request.session_id,
                target_id=request.strategy_id,
                relationship_type="references",
                subsystem="multi_agent"
            )

            if consensus:
                consensus_node_id = f"consensus-{consensus.session_id}"
                kg_orch.register_node(
                    node_id=consensus_node_id,
                    node_type="AGENT_CONSENSUS",
                    subsystem="multi_agent",
                    event="AgentConsensusReached",
                    author="system",
                    properties={"status": consensus.status}
                )
                kg_orch.link_nodes(
                    source_id=consensus_node_id,
                    target_id=request.session_id,
                    relationship_type="references",
                    subsystem="multi_agent"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def execute_session(self, strategy_id: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> AgentConsensus:
        """Orchestrate specialized agent collaborations and compile a consensus recommendation."""
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        request = AgentRequest(
            session_id=session_id,
            strategy_id=strategy_id,
            parameters=parameters,
            context=context
        )
        self._repo.save_session(request)
        self._event_bus.publish(AgentSessionStarted(payload={"session_id": session_id}))

        # Downstream integration for session initialization
        self._publish_memory_record("agent_sessions", request)
        self._update_knowledge_graph(request)

        proposals_so_far: List[AgentProposal] = []

        # 1. Run domain agents (Research, Market, Portfolio, Risk, Execution, Memory, KG)
        domain_agent_types = [
            AgentType.RESEARCH,
            AgentType.MARKET,
            AgentType.PORTFOLIO,
            AgentType.RISK,
            AgentType.EXECUTION,
            AgentType.MEMORY,
            AgentType.KG
        ]

        for atype in domain_agent_types:
            agent = self._agents[atype]
            prop = agent.evaluate_proposal(request, proposals_so_far)
            
            self._repo.save_proposal(session_id, prop)
            self._event_bus.publish(AgentProposalSubmitted(payload={
                "session_id": session_id,
                "agent_type": prop.agent_type.value
            }))
            proposals_so_far.append(prop)

        # 2. Run AI Reviewer to aggregate summaries
        reviewer = self._agents[AgentType.AI_REVIEWER]
        review_prop = reviewer.evaluate_proposal(request, proposals_so_far)
        self._repo.save_proposal(session_id, review_prop)
        self._event_bus.publish(AgentProposalSubmitted(payload={
            "session_id": session_id,
            "agent_type": review_prop.agent_type.value
        }))
        proposals_so_far.append(review_prop)

        # 3. Reconcile final consensus using the precedence rules
        consensus = self._consensus_engine.compile_consensus(session_id, proposals_so_far)
        self._repo.save_consensus(consensus)

        self._event_bus.publish(AgentConsensusReached(payload={
            "session_id": session_id,
            "status": consensus.status
        }))

        # Downstream integration for consensus output
        self._publish_memory_record("agent_consensus", consensus)
        self._update_knowledge_graph(request, consensus)

        return consensus
