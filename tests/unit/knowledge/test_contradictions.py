"""Unit tests for the ContradictionEngine conflict detection algorithms."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from knowledge.contradictions.detector import ContradictionEngine, InvestigationTask
from knowledge.models import Rule, Belief, Evidence, SourceReference, KnowledgeStatus


def test_rule_conflicts_detection():
    """Verify that duplicate conditional rule expressions trigger a rule_conflict task."""
    engine = ContradictionEngine()
    
    r1 = Rule(
        rule_id="r-1",
        name="Trend Buy A",
        rule_type="research",
        expression="trend == 'bullish'",
        confidence_weight=1.0,
        status=KnowledgeStatus.ACTIVE
    )
    r2 = Rule(
        rule_id="r-2",
        name="Trend Buy B (Duplicated Expr)",
        rule_type="research",
        expression="trend == 'bullish'",
        confidence_weight=0.8,
        status=KnowledgeStatus.ACTIVE
    )
    
    tasks = engine.detect_rule_conflicts([r1, r2])
    assert len(tasks) == 1
    assert tasks[0].contradiction_type == "rule_conflict"
    assert "r-1" in tasks[0].offending_ids
    assert "r-2" in tasks[0].offending_ids


def test_belief_conflicts_detection():
    """Verify declared conflicts and semantic opposite checks trigger belief_conflict tasks."""
    engine = ContradictionEngine()
    
    # 1. Declared conflict
    b1 = Belief(
        belief_id="b-1",
        claim="BTC is bullish",
        confidence=0.8,
        conflicting_belief_ids=["b-2"]
    )
    b2 = Belief(
        belief_id="b-2",
        claim="BTC is bearish",
        confidence=0.5,
        conflicting_belief_ids=["b-1"]
    )
    
    tasks_declared = engine.detect_belief_conflicts([b1, b2])
    # The two checks (declared conflicts A-B/B-A and semantic opposite BTC is bullish vs bearish)
    # may trigger multiple tasks. Let's assert at least one conflict task is scheduled.
    assert len(tasks_declared) >= 1
    assert any(t.contradiction_type == "belief_conflict" for t in tasks_declared)
    assert any("b-1" in t.offending_ids for t in tasks_declared)


def test_statistics_conflicts_detection():
    """Verify discrepant statistical metrics from the same source trigger statistics_conflict tasks."""
    engine = ContradictionEngine()
    
    ref = SourceReference(ref_type="experiment", ref_id="exp-99", description="Test")
    
    # Evidence 1 claims Sharpe is 1.8
    ev1 = Evidence(
        evidence_id="ev-1",
        source=ref,
        metric_name="sharpe",
        metric_value=1.8,
        created_at=datetime.now(timezone.utc)
    )
    # Evidence 2 claims Sharpe is 0.5 (discrepant value for same source & metric name)
    ev2 = Evidence(
        evidence_id="ev-2",
        source=ref,
        metric_name="sharpe",
        metric_value=0.5,
        created_at=datetime.now(timezone.utc)
    )
    
    tasks = engine.detect_statistics_conflicts([ev1, ev2])
    assert len(tasks) == 1
    assert tasks[0].contradiction_type == "statistics_conflict"
    assert "ev-1" in tasks[0].offending_ids
    assert "ev-2" in tasks[0].offending_ids
