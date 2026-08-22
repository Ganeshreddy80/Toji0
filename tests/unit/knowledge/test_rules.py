"""Unit tests for the RuleEngine strategy rule registration and evaluation."""

from __future__ import annotations

import pytest

from knowledge.evidence.engine import EvidenceEngine
from knowledge.rules.engine import RuleEngine
from knowledge.models import Rule


def test_rule_requires_evidence():
    """Verify that a rule cannot be registered without evidence IDs."""
    engine = RuleEngine()
    with pytest.raises(ValueError, match="must cite at least one evidence"):
        engine.register_rule(
            name="No Evidence Rule",
            rule_type="risk",
            expression="vol > 10",
            evidence_ids=[],
        )


def test_rule_evidence_validation():
    """Verify rule engine rejects rules referencing unregistered evidence."""
    ev_engine = EvidenceEngine()
    rule_engine = RuleEngine(evidence_engine=ev_engine)
    
    # Attempting to link non-existent evidence should raise ValueError
    with pytest.raises(ValueError, match="does not exist in the evidence engine"):
        rule_engine.register_rule(
            name="Invalid Link Rule",
            rule_type="regime",
            expression="rsi < 30",
            evidence_ids=["missing-evidence-id"],
        )
        
    # Register evidence first, then register rule -> should succeed
    ev = ev_engine.register_evidence(
        source_type="backtest",
        source_id="run-1",
        description="Historical backtest",
        metric_name="sharpe",
        metric_value=1.5
    )
    
    rule = rule_engine.register_rule(
        name="Valid Link Rule",
        rule_type="regime",
        expression="rsi < 30",
        evidence_ids=[ev.evidence_id]
    )
    
    assert isinstance(rule, Rule)
    assert rule.name == "Valid Link Rule"
    assert rule.evidence_ids == [ev.evidence_id]


def test_evaluate_rules():
    """Verify rule evaluation triggers under matching and non-matching facts."""
    rule_engine = RuleEngine()
    
    # Register simple rules (no evidence check when evidence_engine is None)
    r1 = rule_engine.register_rule("Buy Trend", "research", "trend == 'bullish' and vwap_dist < 0.02", ["ev-1"])
    r2 = rule_engine.register_rule("Stop Loss", "risk", "drawdown > max_drawdown", ["ev-2"])
    
    # 1. Matching facts for r1, not r2
    facts1 = {
        "trend": "bullish",
        "vwap_dist": 0.01,
        "drawdown": 0.02,
        "max_drawdown": 0.05
    }
    results1 = rule_engine.evaluate_rules(facts1)
    assert results1[r1.rule_id] is True
    assert results1[r2.rule_id] is False
    
    # 2. Matching facts for r2, not r1
    facts2 = {
        "trend": "bearish",
        "vwap_dist": 0.01,
        "drawdown": 0.07,
        "max_drawdown": 0.05
    }
    results2 = rule_engine.evaluate_rules(facts2)
    assert results2[r1.rule_id] is False
    assert results2[r2.rule_id] is True
