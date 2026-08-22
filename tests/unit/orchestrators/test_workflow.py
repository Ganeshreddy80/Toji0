"""Unit tests for the Workflow Engine."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from orchestrators.workflow_engine.engine import WorkflowEngine
from toji_platform.core.event_bus import InMemoryEventBus


def test_workflow_engine_steps() -> None:
    """Verify that WorkflowEngine executes steps and dispatches StepExecuted events."""
    bus = InMemoryEventBus()
    market = MagicMock()
    research = MagicMock()
    learning = MagicMock()
    dashboard = MagicMock()

    dashboard.get_market_pulses.return_value = {"BTC/USDT": {}}
    dashboard.get_performance_summary.return_value = {"total_decisions": 0, "correct_decisions": 0, "correctness_ratio": 0.0}
    dashboard.get_active_alerts.return_value = []

    engine = WorkflowEngine(
        event_bus=bus,
        market_orch=market,
        research_orch=research,
        learning_orch=learning,
        dashboard_orch=dashboard,
    )

    events = []
    bus.subscribe("system.workflow_step_executed", events.append)

    # 1. Test Morning Briefing
    engine.execute_morning_briefing(["BTC/USDT"])
    assert len(events) == 2
    assert events[0].payload["workflow_name"] == "MorningBriefing"
    assert events[0].payload["step_name"] == "alert_sent"
    assert events[1].payload["step_name"] == "compile_pulses"

    # 2. Test Opportunity Ranking
    events.clear()
    opps = [{"symbol": "BTC/USDT", "score": 0.9}, {"symbol": "ETH/USDT", "score": 0.7}]
    ranked = engine.execute_opportunity_ranking(opps)
    assert len(ranked) == 2
    assert ranked[0]["symbol"] == "BTC/USDT"
    assert len(events) == 1
    assert events[0].payload["step_name"] == "opportunities_sorted"

    # 3. Test End of Day Report compiling
    report = engine.execute_end_of_day_report()
    assert "# TOJI End of Day Performance Report" in report
