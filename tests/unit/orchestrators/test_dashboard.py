"""Unit tests for the Dashboard Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from orchestrators.dashboard_orchestrator.dashboard import DashboardOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import DecisionGenerated, MarketDataUpdated


def test_dashboard_orchestrator_updates() -> None:
    """Verify that DashboardOrchestrator correctly caches pulses, alerts, and performance data from events."""
    bus = InMemoryEventBus()
    db = DashboardOrchestrator(bus)

    # 1. Test MarketDataUpdated handling
    bus.publish(
        MarketDataUpdated(
            source="Test",
            payload={"symbol": "ETH/USDT", "prices": [3000.0, 3050.0], "volumes": [100.0, 120.0]},
        )
    )
    pulses = db.get_market_pulses()
    assert "ETH/USDT" in pulses
    assert pulses["ETH/USDT"]["last_price"] == 3050.0

    # 2. Test DecisionGenerated handling (with ENTER state triggering warning alert)
    bus.publish(
        DecisionGenerated(
            source="Test",
            payload={
                "decision_id": "dec-123",
                "symbol": "ETH/USDT",
                "recommendation": "ENTER",
                "overall_score": 0.8,
                "confidence": 0.9,
            },
        )
    )
    summary = db.get_performance_summary()
    assert summary["total_decisions"] == 1

    alerts = db.get_active_alerts()
    assert len(alerts) == 1
    assert "Action recommended: ENTER" in alerts[0]["message"]

    timeline = db.get_decision_timeline("dec-123")
    assert len(timeline) == 1
    assert timeline[0]["state"] == "Created"
