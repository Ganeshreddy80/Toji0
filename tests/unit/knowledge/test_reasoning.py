"""Unit tests for the ReasoningEngine proof path query tracers."""

from __future__ import annotations

import pytest

from knowledge.evidence.engine import EvidenceEngine
from knowledge.beliefs.engine import BeliefEngine
from knowledge.rules.engine import RuleEngine
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.graph.manager import KnowledgeGraph


def test_explain_rule():
    """Verify rule explanation formatting covers rule info and evidence details."""
    ev_engine = EvidenceEngine()
    rule_engine = RuleEngine(evidence_engine=ev_engine)
    
    ev = ev_engine.register_evidence(
        source_type="backtest",
        source_id="run-100",
        description="Daily trend backtest",
        metric_name="sharpe",
        metric_value=1.8,
        sample_size=150
    )
    
    rule = rule_engine.register_rule(
        name="EMA Breakout",
        rule_type="research",
        expression="close > ema_50",
        evidence_ids=[ev.evidence_id],
        confidence_weight=0.85
    )
    
    explanation = ReasoningEngine.explain_rule(rule.rule_id, rule_engine, ev_engine)
    
    assert "EMA Breakout" in explanation
    assert "close > ema_50" in explanation
    assert "0.85" in explanation
    assert "sharpe = 1.8" in explanation
    assert "sample size=150" in explanation


def test_explain_belief():
    """Verify belief explanation formatting covers claims, statuses, and conflicts."""
    ev_engine = EvidenceEngine()
    belief_engine = BeliefEngine()
    
    ev = ev_engine.register_evidence("experiment", "exp-200", "Details", "t_stat", 2.5)
    belief = belief_engine.create_belief("BTC is ranging", [ev.evidence_id], 0.6)
    
    explanation = ReasoningEngine.explain_belief(belief.belief_id, belief_engine, ev_engine)
    
    assert "BTC is ranging" in explanation
    assert "Active" in explanation
    assert "0.60" in explanation
    assert "t_stat = 2.5" in explanation


def test_find_lineage_path():
    """Verify BFS lineage traversal finds standard multi-hop linkages."""
    graph = KnowledgeGraph()
    graph.add_node("BTC", "Asset")
    graph.add_node("StratA", "Strategy")
    graph.add_node("RuleX", "Rule")
    
    graph.add_edge("BTC", "StratA", "applies_to")
    graph.add_edge("StratA", "RuleX", "uses_rule")
    
    path = ReasoningEngine.find_lineage_path("BTC", "RuleX", graph)
    assert path == ["BTC", "StratA", "RuleX"]


def test_get_active_rules_for_facts():
    """Verify active rules filtration matching factual conditions."""
    rule_engine = RuleEngine()
    
    r1 = rule_engine.register_rule("Rule 1", "risk", "vol > 30", ["ev-1"])
    r2 = rule_engine.register_rule("Rule 2", "risk", "vol < 10", ["ev-2"])
    
    active = ReasoningEngine.get_active_rules_for_facts(rule_engine, {"vol": 35})
    
    assert len(active) == 1
    assert active[0].rule_id == r1.rule_id
