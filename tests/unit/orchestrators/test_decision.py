"""Unit tests for the Decision Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from decision.explainability.engine import ExplainabilityEngine
from decision.journal.manager import DecisionJournal
from decision.voting.engine import InvestmentCommittee
from orchestrators.decision_orchestrator.decision import DecisionOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataUpdated


def test_decision_orchestrator_pipeline() -> None:
    """Verify that DecisionOrchestrator triggers consensus voting on market updates."""
    bus = InMemoryEventBus()
    ic = InvestmentCommittee()
    journal = DecisionJournal()
    exp_engine = ExplainabilityEngine()

    orch = DecisionOrchestrator(
        event_bus=bus,
        investment_committee=ic,
        decision_journal=journal,
        explainability_engine=exp_engine,
    )

    events = []
    bus.subscribe("system.decision_generated", events.append)

    # Publish mock MarketDataUpdated event
    payload = {
        "symbol": "BTC/USDT",
        "interval": "1h",
        "prices": [100.0, 102.0, 105.0],
        "volumes": [10.0, 12.0, 15.0],
        "features": {},
        "sharpe": 2.5,
        "win_rate": 0.65,
    }
    event = MarketDataUpdated(source="Test", payload=payload)
    bus.publish(event)

    assert len(events) == 1
    assert events[0].payload["symbol"] == "BTC/USDT"
    assert events[0].payload["recommendation"] == "ENTER"

    # Verify decision exists in journal
    dec_id = events[0].payload["decision_id"]
    assert journal.get_entry(dec_id) is not None
