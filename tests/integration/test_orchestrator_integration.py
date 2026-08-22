"""End-to-end integration tests for the TOJI system orchestrators."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from data.feature_store import FeatureCache, FeatureRegistry, EMAFeature, RSIFeature
from data.providers.implementations import BinanceProvider
from data.quality.analyzer import DataQualityAnalyzer
from decision.explainability.engine import ExplainabilityEngine
from decision.journal.manager import DecisionJournal
from decision.voting.engine import InvestmentCommittee
from knowledge.beliefs.engine import BeliefEngine
from knowledge.evidence.engine import EvidenceEngine
from knowledge.rules.engine import RuleEngine
from orchestrators.dashboard_orchestrator.dashboard import DashboardOrchestrator
from orchestrators.decision_orchestrator.decision import DecisionOrchestrator
from orchestrators.learning_orchestrator.learning import LearningOrchestrator
from orchestrators.market_orchestrator.market import MarketOrchestrator
from orchestrators.research_orchestrator.research import ResearchOrchestrator
from orchestrators.scheduler.scheduler import Scheduler
from orchestrators.workflow_engine.engine import WorkflowEngine
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.types import AssetClass


class MockAsset:
    """Mock asset to satisfy AssetRegistry schema requirements."""

    def __init__(self, symbol: str, asset_class: AssetClass) -> None:
        self.symbol = symbol
        self.asset_class = asset_class


def test_end_to_end_event_driven_flow() -> None:
    """Verify that all orchestrators work together via events to process data, compile decisions, update dashboard, and audit outcomes."""
    # ── 1. Bootstrap all modules ──
    bus = InMemoryEventBus()
    provider = BinanceProvider()
    cache = FeatureCache()
    registry = FeatureRegistry()

    # Register default features
    registry.register(EMAFeature())
    registry.register(RSIFeature())

    quality = DataQualityAnalyzer()
    ev_engine = EvidenceEngine()
    rule_engine = RuleEngine(evidence_engine=ev_engine)
    belief_engine = BeliefEngine()

    ic = InvestmentCommittee()
    journal = DecisionJournal()
    exp_engine = ExplainabilityEngine()

    # ── 2. Bootstrap system orchestrators ──
    market_orch = MarketOrchestrator(
        event_bus=bus,
        provider=provider,
        feature_cache=cache,
        feature_registry=registry,
        quality_analyzer=quality,
    )

    research_orch = ResearchOrchestrator(
        event_bus=bus,
        experiment_manager=MagicMock_ExperimentManager_stub(),  # stubbed since we don't run research directly in market loop
        evidence_engine=ev_engine,
        rule_engine=rule_engine,
        belief_engine=belief_engine,
    )

    # Setup knowledge engine pre-requisites: register active rule and belief
    mock_ev = ev_engine.register_evidence(
        source_type="backtest",
        source_id="exp-alpha",
        description="Stats check",
        metric_name="sharpe",
        metric_value=2.4,
    )
    rule = rule_engine.register_rule(
        name="EMA-Breakout",
        rule_type="technical",
        expression="close > ema",
        evidence_ids=[mock_ev.evidence_id],
    )
    belief = belief_engine.create_belief(
        claim="Assets trending above EMA go up",
        evidence_ids=[mock_ev.evidence_id],
    )

    # Override the market payload data context when decision_orch processes it so it maps correctly
    def hook_market_event(event) -> None:
        # Inject rule_references and research_references in the event payload
        event.payload["rule_references"] = [rule.rule_id]
        event.payload["research_references"] = [belief.belief_id]

    bus.subscribe("system.market_data_updated", hook_market_event)

    decision_orch = DecisionOrchestrator(
        event_bus=bus,
        investment_committee=ic,
        decision_journal=journal,
        explainability_engine=exp_engine,
    )

    learning_orch = LearningOrchestrator(
        event_bus=bus,
        decision_journal=journal,
        evidence_engine=ev_engine,
        rule_engine=rule_engine,
        belief_engine=belief_engine,
    )

    dashboard_orch = DashboardOrchestrator(event_bus=bus)

    workflow_engine = WorkflowEngine(
        event_bus=bus,
        market_orch=market_orch,
        research_orch=research_orch,
        learning_orch=learning_orch,
        dashboard_orch=dashboard_orch,
    )

    scheduler = Scheduler(event_bus=bus)

    # ── 3. Step 1: Trigger Scheduler Tick ──
    ticks = []
    bus.subscribe("system.scheduler_tick", ticks.append)
    scheduler.trigger_hourly()
    assert len(ticks) == 1
    assert ticks[0].payload["tick_type"] == "hourly"

    # ── 4. Step 2: Trigger Market Scan ──
    # Create market update event and let the workflow execute it.
    start = datetime(2026, 6, 25, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 25, 4, 0, tzinfo=timezone.utc)

    workflow_engine.execute_continuous_market_scan(["BTC/USDT"], "1h", start, end)

    # At this point, the market scan finished processing, published system.market_data_updated.
    # decision_orch intercepted it, ran the committees consensus, logged a decision in journal, and published system.decision_generated.
    # dashboard_orch intercepted system.decision_generated and cached the state.

    summary = dashboard_orch.get_performance_summary()
    assert summary["total_decisions"] == 1
    assert summary["correct_decisions"] == 0  # not audited yet

    pulses = dashboard_orch.get_market_pulses()
    assert "BTC/USDT" in pulses

    alerts = dashboard_orch.get_active_alerts()
    assert len(alerts) >= 1
    assert any("Action recommended: ENTER" in a["message"] for a in alerts)

    # Retrieve decision ID
    decision_entries = list(journal._entries.values())
    assert len(decision_entries) == 1
    dec_id = decision_entries[0].decision_id

    timeline = dashboard_orch.get_decision_timeline(dec_id)
    assert len(timeline) == 1
    assert timeline[0]["state"] == "Created"

    # ── 5. Step 3: Trigger Daily Learning & Audits ──
    # The asset price rose from 100.0 to 110.0 (Buy decision was correct!)
    workflow_engine.execute_daily_learning({dec_id: [100.0, 110.0]})

    # dashboard_orch updates timeline of dec_id to Closed
    timeline_updated = dashboard_orch.get_decision_timeline(dec_id)
    assert len(timeline_updated) == 2
    assert timeline_updated[1]["state"] == "Closed"

    # stats update: correct_decisions goes to 1
    summary_updated = dashboard_orch.get_performance_summary()
    assert summary_updated["total_decisions"] == 1
    assert summary_updated["correct_decisions"] == 1
    assert summary_updated["correctness_ratio"] == 1.0

    # Rule confidence weight evolved with new audit evidence
    updated_rule = rule_engine.get_rule(rule.rule_id)
    assert len(updated_rule.evidence_ids) == 2  # Original evidence + new audit evidence
    assert updated_rule.confidence_weight > 0.0


class MagicMock_ExperimentManager_stub:
    """Minimal stub class for experiment manager."""

    def __init__(self) -> None:
        pass
