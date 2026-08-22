"""Consensus compiler reconciling conflicts across agent proposals.
"""

from __future__ import annotations

import logging
from typing import List
from research_platform.multi_agent.models import AgentConsensus, AgentProposal, AgentType

logger = logging.getLogger(__name__)


class AgentConsensusEngine:
    """Aggregates multiple agent proposals and applies role-based precedence rules to resolve conflicts."""

    def compile_consensus(self, session_id: str, proposals: List[AgentProposal]) -> AgentConsensus:
        """Compile a unified recommendation, applying precedence rules (RISK has highest priority)."""
        final_recommendation = {}
        status = "APPROVED"

        # Precedence map: higher values mean higher priority
        precedence = {
            AgentType.RISK: 100,
            AgentType.MARKET: 80,
            AgentType.RESEARCH: 60,
            AgentType.PORTFOLIO: 50,
            AgentType.EXECUTION: 40,
            AgentType.MEMORY: 30,
            AgentType.KG: 20,
            AgentType.AI_REVIEWER: 10
        }

        # Tracks which agent type set which recommendation key
        key_source = {}

        for prop in proposals:
            # If Risk agent suggests high caution (e.g., drawdown is critical), we can reject
            if prop.agent_type == AgentType.RISK:
                # If risk agent indicates severe breach (e.g. stop loss extremely tight)
                if prop.advisory_recommendations.get("trading_halt_limit") is not None:
                    status = "REJECTED"

            # Merge recommendations with conflict resolution
            for key, val in prop.advisory_recommendations.items():
                if key not in final_recommendation:
                    final_recommendation[key] = val
                    key_source[key] = prop.agent_type
                else:
                    # Conflict: resolve using precedence map
                    current_source = key_source[key]
                    current_priority = precedence.get(current_source, 0)
                    new_priority = precedence.get(prop.agent_type, 0)

                    if new_priority > current_priority:
                        final_recommendation[key] = val
                        key_source[key] = prop.agent_type

        # Inject AI Reviewer's summary collation into final recommendation
        ai_prop = next((p for p in proposals if p.agent_type == AgentType.AI_REVIEWER), None)
        if ai_prop:
            final_recommendation["reviewer_notes"] = ai_prop.rationale

        logger.info("Compiled consensus for session '%s': Status=%s, Recs Keys=%s",
                    session_id, status, list(final_recommendation.keys()))

        return AgentConsensus(
            session_id=session_id,
            proposals=proposals,
            final_recommendation=final_recommendation,
            status=status
        )
