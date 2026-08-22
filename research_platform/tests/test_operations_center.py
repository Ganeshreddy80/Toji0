"""Unit and integration tests for the TOJI Institutional Operations Center.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator
from research_platform.operations_center.repository import OperationsRepository
from research_platform.operations_center.dashboard_models import DashboardSnapshot

# Subsystem dependencies
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    trading_orch = PaperTradingOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator", instance=trading_orch)

    market_orch = PaperMarketOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_market.orchestrator.PaperMarketOrchestrator", instance=market_orch)

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return OperationsOrchestrator(event_bus, container=container)


def test_dashboard_snapshot_aggregation(orchestrator, container):
    """Verify that dashboard compiles all subsystem widget states."""
    # Start paper session to establish portfolio metrics
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-1", 100000.0)

    # Compile snapshot
    snapshot = orchestrator.compile_dashboard_snapshot()
    assert isinstance(snapshot, DashboardSnapshot)
    assert snapshot.portfolio.cash == 100000.0
    assert snapshot.health.status == "HEALTHY"
    assert snapshot.risk.kill_switch_active is False
    assert snapshot.simulation.status == "SUCCESS"


def test_high_drawdown_critical_alert_generation(orchestrator, container, event_bus):
    """Verify that drawdown breach triggers priority warnings and events."""
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-1", 100000.0)

    # Establish an asset position and then simulate a massive negative price tick update
    paper_orch.submit_paper_order("s1", "AAPL", 1000, 0.0, "MARKET", "BUY", "Buy check")
    # Ticks AAPL down to 10.0 to trigger > 10% drawdown
    paper_orch.update_market_price("AAPL", 10.0)

    events = []
    event_bus.subscribe("system.operational_alert_triggered", events.append)

    # Refreshes snap
    orchestrator.compile_dashboard_snapshot()

    # Verify critical alert logged
    active_alerts = orchestrator.repository.list_active_alerts()
    assert len(active_alerts) == 1
    assert active_alerts[0].priority == "CRITICAL"
    assert "High drawdown" in active_alerts[0].message
    assert len(events) == 1


def test_historical_snapshots_playback(orchestrator):
    """Verify storing rolling snapshot history and lists retrieval."""
    repo = orchestrator.repository
    repo.clear_all()

    # Compile 3 distinct snapshots
    orchestrator.compile_dashboard_snapshot()
    orchestrator.compile_dashboard_snapshot()
    orchestrator.compile_dashboard_snapshot()

    snaps = repo.list_historical_snapshots()
    assert len(snaps) == 3
