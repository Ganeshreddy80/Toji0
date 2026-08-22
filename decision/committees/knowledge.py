"""Knowledge Committee implementation for evaluating rule evidence and conflicts."""

from __future__ import annotations

from typing import Any
from decision.committees.base import BaseCommittee
from decision.models import CommitteeVote, DecisionState


class KnowledgeCommittee(BaseCommittee):
    """Evaluates rule weights, supporting evidence volumes, graph contradictions, and freshness context."""

    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Evaluate knowledge graph criteria and submit a vote.

        Args:
            context: Context containing 'rule_confidence_weight', 'evidence_count',
                     'active_contradictions_count', and 'knowledge_freshness'.

        Returns:
            CommitteeVote.
        """
        rule_conf = context.get("rule_confidence_weight", 0.70)
        evidence_cnt = context.get("evidence_count", 1)
        contradictions = context.get("active_contradictions_count", 0)
        freshness = context.get("knowledge_freshness", 0.80)

        metrics = {
            "rule_confidence_weight": rule_conf,
            "evidence_count": evidence_cnt,
            "active_contradictions_count": contradictions,
            "knowledge_freshness": freshness,
        }

        # High graph contradiction -> Ignore/Reduce
        if contradictions > 0:
            return CommitteeVote(
                committee_name="Knowledge",
                vote_state=DecisionState.IGNORE,
                score=0.10,
                confidence=0.90,
                metrics=metrics,
                reason=f"Active contradictions detected ({contradictions}) on this asset's rules/beliefs",
            )

        # Unsupported or low confidence rules
        if evidence_cnt == 0 or rule_conf < 0.40:
            return CommitteeVote(
                committee_name="Knowledge",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.70,
                metrics=metrics,
                reason=f"Insufficient supporting evidence (count={evidence_cnt}) or rule confidence too low ({rule_conf:.2f})",
            )

        # High support with fresh evidence
        if rule_conf >= 0.80 and evidence_cnt >= 3 and freshness >= 0.70:
            return CommitteeVote(
                committee_name="Knowledge",
                vote_state=DecisionState.ENTER,
                score=0.90,
                confidence=0.90,
                metrics=metrics,
                reason="Fresh, highly supported rules back this asset with zero active contradictions",
            )

        # Moderate support
        return CommitteeVote(
            committee_name="Knowledge",
            vote_state=DecisionState.READY,
            score=0.65,
            confidence=0.80,
            metrics=metrics,
            reason="Acceptable rule confidence and evidence support",
        )
