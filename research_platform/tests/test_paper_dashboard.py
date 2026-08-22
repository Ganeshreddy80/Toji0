"""Unit and integration tests for the TOJI Institutional Dashboard & Paper Control Console.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.paper_dashboard.orchestrator import PaperDashboardOrchestrator
from research_platform.paper_dashboard.console_controller import ConsoleController
from research_platform.paper_dashboard.repository import PaperDashboardRepository

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
    return PaperDashboardOrchestrator(event_bus, container=container)


@pytest.fixture
def controller(orchestrator):
    return ConsoleController(orchestrator)


def test_console_command_parsing(controller, orchestrator):
    """Verify text-based commands execute successfully."""
    # 1. Start session command
    res_start = controller.execute_command_text("START_SESSION acc-1 100000")
    assert "SUCCESS" in res_start
    assert orchestrator.paper_trading.active_session is not None
    assert orchestrator.paper_trading.active_session.account.cash == 100000.0

    # 2. Change router mode
    res_mode = controller.execute_command_text("SET_ROUTING_MODE SIMULATION")
    assert "SUCCESS" in res_mode
    assert orchestrator.paper_market.execution_router.mode == "SIMULATION"

    # 3. Show metrics
    res_metrics = controller.execute_command_text("SHOW_METRICS")
    assert "Equity" in res_metrics
    assert "Routing Mode: SIMULATION" in res_metrics

    # Check repository command log history
    cmds = orchestrator.repository.list_commands()
    assert len(cmds) == 3
    assert cmds[0].command_name == "START_SESSION"
    assert cmds[1].command_name == "SET_ROUTING_MODE"
    assert cmds[2].command_name == "SHOW_METRICS"

    # 4. Stop session
    res_stop = controller.execute_command_text("STOP_SESSION")
    assert "SUCCESS" in res_stop
    assert orchestrator.paper_trading.active_session is None


def test_invalid_command_failures(controller):
    """Verify invalid syntax or unsupported commands fail gracefully with error outputs."""
    res_invalid = controller.execute_command_text("START_SESSION acc-1")
    assert "ERROR" in res_invalid

    res_unknown = controller.execute_command_text("INVALID_COMMAND")
    assert "ERROR" in res_unknown
