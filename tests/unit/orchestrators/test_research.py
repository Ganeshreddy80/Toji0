"""Unit tests for the Research Orchestrator."""

from __future__ import annotations

import pytest

from knowledge.beliefs.engine import BeliefEngine
from knowledge.evidence.engine import EvidenceEngine
from knowledge.rules.engine import RuleEngine
from orchestrators.research_orchestrator.research import ResearchOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus
from research.experiments.manager import ExperimentManager


def test_research_orchestrator_pipeline() -> None:
    """Verify that ResearchOrchestrator runs the experiment lifecycle and registers knowledge rules."""
    bus = InMemoryEventBus()
    exp_mgr = ExperimentManager()
    ev_engine = EvidenceEngine()
    rule_engine = RuleEngine(evidence_engine=ev_engine)
    belief_engine = BeliefEngine()

    orch = ResearchOrchestrator(
        event_bus=bus,
        experiment_manager=exp_mgr,
        evidence_engine=ev_engine,
        rule_engine=rule_engine,
        belief_engine=belief_engine,
    )

    events = []
    bus.subscribe("system.research_completed", events.append)

    metrics = {"sharpe": 2.1, "p_value": 0.005}
    outcome = orch.execute_experiment_pipeline(
        name="Momentum Alpha",
        description="Testing trend momentum significance",
        dataset_ref="daily-bars-v1",
        asset_universe=["BTC/USDT", "ETH/USDT"],
        feature_refs=["RSI", "EMA"],
        metrics=metrics,
        rule_expression="rsi > 50 and close > ema",
        belief_claim="Momentum is historically positive under high indicators",
    )

    assert len(events) == 1
    assert outcome["status"] == "success"
    assert len(outcome["evidence_ids"]) == 2
    assert len(outcome["rule_ids"]) == 1
    assert len(outcome["belief_ids"]) == 1

    # Verify nodes exist in engines
    assert rule_engine.get_rule(outcome["rule_ids"][0]) is not None
    assert belief_engine.get_belief(outcome["belief_ids"][0]) is not None
