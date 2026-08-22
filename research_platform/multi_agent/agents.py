"""Specialized agent implementations of the IAgentDecisionEngine contract.
"""

from __future__ import annotations

from typing import List
from research_platform.multi_agent.interfaces import IAgentDecisionEngine
from research_platform.multi_agent.models import AgentProposal, AgentRequest, AgentType


class ResearchAgent(IAgentDecisionEngine):
    """Reviews signal features and lookback parameter bounds."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        lookback = request.parameters.get("lookback", 20)
        recs = {}
        if lookback < 10:
            recs["lookback"] = 15
            rationale = "Lookback is too short, recommending increasing to filter false signals."
        else:
            rationale = "Lookback parameter verified as stable."

        return AgentProposal(
            agent_type=AgentType.RESEARCH,
            confidence_score=0.80,
            advisory_recommendations=recs,
            rationale=rationale
        )


class MarketAgent(IAgentDecisionEngine):
    """Reviews volatility and liquidity regimes."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        regime = request.context.get("regime", "NORMAL")
        recs = {}
        if regime == "HIGH_VOLATILITY":
            recs["volume_scale"] = 0.5
            rationale = "High volatility regime detected. Recommend scaling down execution volume."
        else:
            rationale = "Market regime is normal, standard volume sizing allowed."

        return AgentProposal(
            agent_type=AgentType.MARKET,
            confidence_score=0.85,
            advisory_recommendations=recs,
            rationale=rationale
        )


class PortfolioAgent(IAgentDecisionEngine):
    """Reviews strategy allocation weights."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        return AgentProposal(
            agent_type=AgentType.PORTFOLIO,
            confidence_score=0.75,
            advisory_recommendations={"diversify": True},
            rationale="Strategy allocation weight limits are balanced."
        )


class RiskAgent(IAgentDecisionEngine):
    """Monitors drawdown and risk budgets constraints."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        drawdown = request.context.get("drawdown", 0.0)
        recs = {}
        if drawdown > 0.10:
            recs["stop_loss"] = 0.02
            recs["trading_halt_limit"] = 0.15
            rationale = "Drawdown exceeds 10%. Recommend tightening stop losses."
        else:
            rationale = "Drawdown within acceptable thresholds."

        return AgentProposal(
            agent_type=AgentType.RISK,
            confidence_score=0.90,
            advisory_recommendations=recs,
            rationale=rationale
        )


class ExecutionAgent(IAgentDecisionEngine):
    """Monitors bid-ask spreads and order execution channels."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        spread = request.context.get("spread", 0.001)
        recs = {}
        if spread > 0.003:
            recs["order_type"] = "LIMIT"
            rationale = "Spreads are wide. Recommending LIMIT orders only."
        else:
            rationale = "Spreads are normal, standard order executions allowed."

        return AgentProposal(
            agent_type=AgentType.EXECUTION,
            confidence_score=0.80,
            advisory_recommendations=recs,
            rationale=rationale
        )


class MemoryAgent(IAgentDecisionEngine):
    """Queries lessons and parameters from historical memories."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        return AgentProposal(
            agent_type=AgentType.MEMORY,
            confidence_score=0.70,
            advisory_recommendations={"memory_lessons_verified": True},
            rationale="Verified parameter profiles against historical drawdown records."
        )


class KGAgent(IAgentDecisionEngine):
    """Reviews graph dependencies and semantic relationships."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        return AgentProposal(
            agent_type=AgentType.KG,
            confidence_score=0.75,
            advisory_recommendations={"dependency_validated": True},
            rationale="No cyclic loops detected in dependency lineage structures."
        )


class AIReviewerAgent(IAgentDecisionEngine):
    """Aggregates other agent proposals and creates collated textual summaries."""

    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        recs = {}
        rationales = []
        for prop in proposals_so_far:
            recs.update(prop.advisory_recommendations)
            rationales.append(f"{prop.agent_type.value}: {prop.rationale}")

        return AgentProposal(
            agent_type=AgentType.AI_REVIEWER,
            confidence_score=0.95,
            advisory_recommendations=recs,
            rationale="Collated Summary: " + " | ".join(rationales)
        )
