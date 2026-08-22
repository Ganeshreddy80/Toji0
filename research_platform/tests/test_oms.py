"""Unit and integration tests for the TOJI Institutional Order Management System (OMS).
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.oms.oms_core import OmsCore
from research_platform.oms.models import Order, Fill, ExecutionReport

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
def oms(event_bus, container):
    return OmsCore(event_bus, container=container)


def test_oms_order_lifecycle_fill_workflow(oms, container):
    """Verify NEW -> VALIDATED -> QUEUED -> ROUTED -> FILLED transition paths."""
    # Active paper session is required for paper executions
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    # Submit MARKET order -> fills immediately
    order = oms.submit_order(
        strategy_id="strat-alpha",
        symbol="AAPL",
        quantity=10,
        price=0.0,
        order_type="MARKET",
        side="BUY",
        rationale="Lifecycle validation check"
    )

    assert order.status == "FILLED"
    assert order.executed_price == 100.01
    assert order.executed_quantity == 10

    # Verify history logs in repository
    history = oms.repository.get_order_history(order.order_id)
    assert history == ["NEW", "VALIDATED", "QUEUED", "ROUTED", "FILLED"]

    # Verify fill recorded
    fills = oms.repository.list_fills(order.order_id)
    assert len(fills) == 1
    assert fills[0].quantity == 10


def test_oms_order_limit_checks_rejection(oms):
    """Verify limit validation check blocks negative or blank orders immediately."""
    # Negative quantity
    ord_neg = oms.submit_order("s1", "AAPL", -5.0, 0.0, "MARKET", "BUY", "Negative Qty check")
    assert ord_neg.status == "REJECTED"

    # Blank symbol
    ord_blank = oms.submit_order("s1", "", 10.0, 0.0, "MARKET", "BUY", "Blank symbol check")
    assert ord_blank.status == "REJECTED"


def test_oms_duplicate_order_prevention(oms, container):
    """Verify matching order submissions in rapid succession trigger duplicate blocks."""
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    # 1. First order completes successfully
    ord_1 = oms.submit_order("s1", "AAPL", 10, 0.0, "MARKET", "BUY", "First order")
    assert ord_1.status == "FILLED"

    # 2. Identical duplicate order submitted immediately triggers REJECTED state
    ord_2 = oms.submit_order("s1", "AAPL", 10, 0.0, "MARKET", "BUY", "Duplicate order")
    assert ord_2.status == "REJECTED"


def test_oms_queue_depth_metrics(oms, container):
    """Verify queue depths and telemetry aggregations reports are accurate."""
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    oms.submit_order("s1", "AAPL", 10, 0.0, "MARKET", "BUY", "Fill order")
    oms.submit_order("s1", "", 10, 0.0, "MARKET", "BUY", "Reject order")

    depths = oms.repository.get_queue_depth()
    assert depths["FILLED"] == 1
    assert depths["REJECTED"] == 1

    metrics = oms.get_performance_metrics()
    assert metrics["fill_ratio"] == 0.5
    assert metrics["reject_ratio"] == 0.5


def test_oms_consolidation_and_compatibility(container, event_bus):
    """Verify that OmsCore registers under both types and implements ingest_order."""
    from research_platform.oms.plugin import OmsPlugin
    from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
    from research_platform.oms.models import OrderRequest

    # Initialize the plugin on a clean container
    plugin = OmsPlugin(container)
    plugin.initialize()

    # Verify both resolutions return the exact same instance
    oms_core_instance = container.resolve(OmsCore)
    oms_orch_instance = container.resolve("OrderManagementSystemOrchestrator")
    oms_orch_class_instance = container.resolve(OrderManagementSystemOrchestrator)

    assert oms_core_instance is oms_orch_instance
    assert oms_core_instance is oms_orch_class_instance

    # Start active paper session
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    # Verify ingest_order compatibility
    req = OrderRequest(
        order_id="ingest-001",
        symbol="BTCUSDT",
        direction="BUY",
        quantity=0.1,
        order_type="MARKET",
        price=50000.0,
        strategy_id="s1"
    )
    res_order = oms_core_instance.ingest_order(req)
    assert res_order.order_id == "ingest-001"
    assert res_order.status == "FILLED"

