"""Investment Committee engine for voting consensus and regime weights."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from decision.models import CommitteeVote, DecisionState, InvestmentDecision
from decision.committees.research import ResearchCommittee
from decision.committees.risk import RiskCommittee
from decision.committees.portfolio import PortfolioCommittee
from decision.committees.timing import TimingCommittee
from decision.committees.knowledge import KnowledgeCommittee


class InvestmentCommittee:
    """Orchestrates committee evaluations, aggregates votes using regime profiles, and makes final decisions."""

    def __init__(self, custom_profiles: dict[str, dict[str, float]] | None = None) -> None:
        """Initialize the InvestmentCommittee.

        Args:
            custom_profiles: Optional override dictionary of regime -> committee -> weight.
        """
        self.committees = {
            "Research": ResearchCommittee(),
            "Risk": RiskCommittee(),
            "Portfolio": PortfolioCommittee(),
            "Timing": TimingCommittee(),
            "Knowledge": KnowledgeCommittee(),
        }

        # Setup standard regime profiles
        # Weights must sum to 1.0 per profile
        self.profiles = {
            "default": {
                "Research": 0.25,
                "Risk": 0.25,
                "Portfolio": 0.20,
                "Timing": 0.15,
                "Knowledge": 0.15,
            },
            "markup": {
                "Research": 0.30,
                "Risk": 0.20,
                "Portfolio": 0.20,
                "Timing": 0.15,
                "Knowledge": 0.15,
            },
            "markdown": {
                "Risk": 0.50,
                "Timing": 0.20,
                "Portfolio": 0.10,
                "Research": 0.10,
                "Knowledge": 0.10,
            },
            "expansion": {  # High volatility
                "Risk": 0.45,
                "Portfolio": 0.20,
                "Timing": 0.15,
                "Research": 0.10,
                "Knowledge": 0.10,
            },
            "compression": {  # Volatility compression
                "Timing": 0.35,
                "Research": 0.20,
                "Portfolio": 0.20,
                "Risk": 0.15,
                "Knowledge": 0.10,
            },
            "accumulation": {
                "Research": 0.25,
                "Knowledge": 0.25,
                "Portfolio": 0.20,
                "Risk": 0.15,
                "Timing": 0.15,
            },
            "distribution": {
                "Risk": 0.35,
                "Portfolio": 0.25,
                "Timing": 0.15,
                "Research": 0.15,
                "Knowledge": 0.10,
            },
        }

        if custom_profiles:
            for k, v in custom_profiles.items():
                self.profiles[k.lower()] = v

    def _get_profile_weights(self, regime: str) -> dict[str, float]:
        """Retrieve the voting weight profile for a specific regime, falling back to default."""
        return self.profiles.get(regime.strip().lower(), self.profiles["default"])

    def _map_state_to_value(self, state: DecisionState) -> float:
        """Map DecisionState to numerical value for score averaging."""
        mapping = {
            DecisionState.EMERGENCY_EXIT: -1.0,
            DecisionState.EXIT: -0.5,
            DecisionState.REDUCE: -0.3,
            DecisionState.IGNORE: 0.0,
            DecisionState.WATCH: 0.1,
            DecisionState.PREPARE: 0.3,
            DecisionState.READY: 0.6,
            DecisionState.HOLD: 0.8,
            DecisionState.ENTER: 1.0,
        }
        return mapping[state]

    def _map_value_to_state(self, val: float) -> DecisionState:
        """Map synthesized numerical consensus value back to DecisionState."""
        if val >= 0.85:
            return DecisionState.ENTER
        elif val >= 0.70:
            return DecisionState.HOLD
        elif val >= 0.45:
            return DecisionState.READY
        elif val >= 0.25:
            return DecisionState.PREPARE
        elif val >= 0.05:
            return DecisionState.WATCH
        elif val > -0.15:
            return DecisionState.IGNORE
        elif val > -0.45:
            return DecisionState.REDUCE
        elif val > -0.75:
            return DecisionState.EXIT
        else:
            return DecisionState.EMERGENCY_EXIT

    def compile_decision(
        self,
        symbol: str,
        context: dict[str, Any],
        regime: str = "default",
        evaluation_time: datetime | None = None,
    ) -> InvestmentDecision:
        """Collect votes, apply profile weights, check for vetos, and compile final InvestmentDecision.

        Args:
            symbol: Target asset symbol.
            context: Aggregated context data for all committees.
            regime: Current detected market regime.
            evaluation_time: Reference time for evaluation. Defaults to UTC now.

        Returns:
            InvestmentDecision object.
        """
        if evaluation_time is None:
            evaluation_time = datetime.now(timezone.utc)

        # 1. Collect votes from all committees
        votes: list[CommitteeVote] = []
        for name, comm in self.committees.items():
            vote = comm.vote(context)
            votes.append(vote)

        # 2. Retrieve weight profile
        weights = self._get_profile_weights(regime)

        # 3. Calculate weighted overall score, confidence, and mapped consensus
        weighted_score_val = 0.0
        weighted_state_val = 0.0
        weighted_confidence = 0.0

        has_veto = False
        veto_reason = ""
        veto_state = DecisionState.EMERGENCY_EXIT

        for vote in votes:
            w = weights.get(vote.committee_name, 0.20)
            weighted_score_val += w * vote.score
            weighted_state_val += w * self._map_state_to_value(vote.vote_state)
            weighted_confidence += w * vote.confidence

            # Veto triggers: Risk committee calling EMERGENCY_EXIT vetoes entries.
            if vote.vote_state == DecisionState.EMERGENCY_EXIT:
                has_veto = True
                veto_state = DecisionState.EMERGENCY_EXIT
                veto_reason = f"Veto triggered: {vote.committee_name} Committee voted EMERGENCY_EXIT due to: {vote.reason}"
            elif vote.vote_state == DecisionState.EXIT and not has_veto:
                # EXIT vetoes ENTER/READY states
                has_veto = True
                veto_state = DecisionState.EXIT
                veto_reason = f"Veto triggered: {vote.committee_name} Committee voted EXIT due to: {vote.reason}"

        # 4. Final Recommendation State mapping
        if has_veto:
            final_rec = veto_state
            overall_score = -1.0 if veto_state == DecisionState.EMERGENCY_EXIT else -0.5
        else:
            final_rec = self._map_value_to_state(weighted_state_val)
            overall_score = max(-1.0, min(1.0, weighted_score_val))

        # 5. Extract summaries and evidence details
        supporting = context.get("supporting_evidence", [])
        contradicting = context.get("contradicting_evidence", [])
        rules = context.get("rule_references", [])
        research = context.get("research_references", [])

        # Format reports summaries
        risk_vote = next((v for v in votes if v.committee_name == "Risk"), None)
        timing_vote = next((v for v in votes if v.committee_name == "Timing"), None)

        risk_summary = risk_vote.reason if risk_vote else "Risk not evaluated"
        if has_veto and veto_state == DecisionState.EMERGENCY_EXIT:
            risk_summary = f"[VETO ACTIVE] {risk_summary}. {veto_reason}"

        timing_summary = timing_vote.reason if timing_vote else "Timing not evaluated"

        # Expirations & checks
        expiry_seconds = context.get("expiry_seconds", 14400)  # 4 hours default
        review_seconds = context.get("review_seconds", 1800)   # 30 mins default

        expiry_time = evaluation_time + timedelta(seconds=expiry_seconds)
        review_time = evaluation_time + timedelta(seconds=review_seconds)

        return InvestmentDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            overall_score=overall_score,
            final_recommendation=final_rec,
            confidence=max(0.0, min(1.0, weighted_confidence)),
            votes=votes,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            rule_references=rules,
            research_references=research,
            risk_summary=risk_summary,
            timing_summary=timing_summary,
            expiry_time=expiry_time,
            review_time=review_time,
            created_at=evaluation_time,
        )
