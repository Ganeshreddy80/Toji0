"""Unit tests for the Learning Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from decision.journal.manager import DecisionJournal
from decision.models import CommitteeVote, DecisionState, InvestmentDecision
from knowledge.beliefs.engine import BeliefEngine
from knowledge.evidence.engine import EvidenceEngine
from knowledge.rules.engine import RuleEngine
from orchestrators.learning_orchestrator.learning import LearningOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus


def test_learning_orchestrator_pipeline() -> None:
    """Verify that LearningOrchestrator audits decisions and calibrates confidence."""
    bus = InMemoryEventBus()
    journal = DecisionJournal()
    ev_engine = EvidenceEngine()
    rule_engine = RuleEngine(evidence_engine=ev_engine)
    belief_engine = BeliefEngine()

    orch = LearningOrchestrator(
        event_bus=bus,
        decision_journal=journal,
        evidence_engine=ev_engine,
        rule_engine=rule_engine,
        belief_engine=belief_engine,
    )

    events = []
    bus.subscribe("system.learning_completed", events.append)

    # 1. Setup mock evidence, rule, and belief
    ev = ev_engine.register_evidence(
        source_type="experiment",
        source_id="exp-1",
        description="test",
        metric_name="sharpe",
        metric_value=2.0,
    )
    rule = rule_engine.register_rule(
        name="test-rule",
        rule_type="test",
        expression="close > 10",
        evidence_ids=[ev.evidence_id],
    )
    belief = belief_engine.create_belief(
        claim="price goes up",
        evidence_ids=[ev.evidence_id],
    )

    # 2. Log mock decision referencing this rule & belief
    votes = [
        CommitteeVote(
            committee_name="Research",
            vote_state=DecisionState.ENTER,
            score=0.90,
            confidence=0.85,
            reason="Strong metrics",
        )
    ]
    decision = InvestmentDecision(
        decision_id="dec-to-audit",
        symbol="BTC/USDT",
        overall_score=0.85,
        final_recommendation=DecisionState.ENTER,
        confidence=0.85,
        votes=votes,
        rule_references=[rule.rule_id],
        research_references=[belief.belief_id],
        risk_summary="Safe",
        timing_summary="Immediate",
        expiry_time=datetime.now(timezone.utc),
        review_time=datetime.now(timezone.utc),
    )
    journal.log_decision(decision)

    # 3. Perform performance audit (price rose from 100.0 to 105.0)
    is_correct = orch.audit_decision_performance("dec-to-audit", [100.0, 105.0])

    assert is_correct is True
    assert len(events) == 1
    assert events[0].payload["decision_id"] == "dec-to-audit"
    assert events[0].payload["is_correct"] is True

    # Verify rule confidence was calibrated
    updated_rule = rule_engine.get_rule(rule.rule_id)
    assert updated_rule is not None
    assert len(updated_rule.evidence_ids) == 2  # Original evidence + new audit evidence
    assert updated_rule.confidence_weight > 0.0
