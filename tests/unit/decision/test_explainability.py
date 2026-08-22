"""Unit tests for the Explainability Engine."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from decision.models import CommitteeVote, DecisionState, InvestmentDecision
from decision.explainability.engine import ExplainabilityEngine


@pytest.fixture
def engine() -> ExplainabilityEngine:
    """Provide an ExplainabilityEngine instance."""
    return ExplainabilityEngine()


def test_generate_explanation_report(engine: ExplainabilityEngine) -> None:
    """Test generating a markdown explanation from a decision object."""
    votes = [
        CommitteeVote(
            committee_name="Research",
            vote_state=DecisionState.ENTER,
            score=0.90,
            confidence=0.90,
            reason="Strong metrics",
        ),
        CommitteeVote(
            committee_name="Risk",
            vote_state=DecisionState.ENTER,
            score=0.90,
            confidence=0.90,
            reason="Safe drawdown",
        ),
    ]

    decision = InvestmentDecision(
        decision_id="dec-12345",
        symbol="BTC/USDT",
        overall_score=0.90,
        final_recommendation=DecisionState.ENTER,
        confidence=0.90,
        votes=votes,
        supporting_evidence=["Empirical test 1", "Empirical test 2"],
        contradicting_evidence=["Correlation warn"],
        rule_references=["rule-4"],
        research_references=["exp-9"],
        risk_summary="Safe drawdown",
        timing_summary="Immediate active session",
        expiry_time=datetime(2026, 6, 25, 23, 0, 0, tzinfo=timezone.utc),
        review_time=datetime(2026, 6, 25, 19, 30, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 6, 25, 19, 0, 0, tzinfo=timezone.utc),
    )

    report = engine.generate_explanation_report(decision)

    assert "# Investment Recommendation Report: BTC/USDT" in report
    assert "dec-12345" in report
    assert "ENTER" in report
    assert "Safe drawdown" in report
    assert "Empirical test 1" in report
    assert "rule-4" in report
    assert "exp-9" in report
