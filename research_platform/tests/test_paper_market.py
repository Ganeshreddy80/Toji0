"""Unit and integration tests for the TOJI Paper Market Integration & Execution Routing.
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataReceived

from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.paper_market.market_state_cache import MarketStateCache
from research_platform.paper_market.heartbeat_monitor import HeartbeatMonitor
from research_platform.paper_market.paper_execution_router import PaperExecutionRouter

# R28 dependencies
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
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

    paper_orch = PaperTradingOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator", instance=paper_orch)

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return PaperMarketOrchestrator(event_bus, container=container)


def test_market_state_cache_pricing():
    """Verify caching prices and retrieval timestamps."""
    cache = MarketStateCache()
    assert cache.get_price("BTC/USDT") is None

    cache.set_price("BTC/USDT", 65000.0)
    assert cache.get_price("BTC/USDT") == 65000.0
    assert cache.get_last_update_time("BTC/USDT") is not None


def test_heartbeat_feed_freshness():
    """Verify heartbeat monitor detects stale price feed update gaps."""
    cache = MarketStateCache()
    monitor = HeartbeatMonitor(cache)

    assert monitor.check_heartbeat("BTC/USDT") is False

    cache.set_price("BTC/USDT", 65000.0)
    assert monitor.check_heartbeat("BTC/USDT", max_gap_seconds=2.0) is True

    # Artificially delay update
    time.sleep(0.02)
    assert monitor.check_heartbeat("BTC/USDT", max_gap_seconds=0.001) is False


def test_execution_routing_branches(container):
    """Verify simulation and paper execution routing paths are matched."""
    router = PaperExecutionRouter(container=container)

    # 1. Default mode is PAPER
    assert router.mode == "PAPER"
    
    # Under PAPER mode, submitting order requires active paper session
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-demo", 100000.0)

    res_paper = router.route_order("s1", "BTC/USDT", 1.0, 0.0, "MARKET", "BUY", "Routing logic check")
    assert res_paper.status == "FILLED"

    # 2. Change mode to SIMULATION
    router.set_mode("SIMULATION")
    res_sim = router.route_order("s1", "BTC/USDT", 1.0, 0.0, "MARKET", "BUY", "Routing logic check")
    # Returns fallback mock validation
    assert res_sim["status"] == "FILLED"

    # 3. Change mode to LIVE -> raises PermissionError
    router.set_mode("LIVE")
    with pytest.raises(PermissionError):
        router.route_order("s1", "BTC/USDT", 1.0, 0.0, "MARKET", "BUY", "Routing logic check")


def test_orchestrator_market_data_integration_flow(orchestrator, container, event_bus):
    """Verify that incoming events trigger cache updates, position updates and drawdowns."""
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    # Place a MARKET BUY order to establish a position
    # Price will match at 100.01 (slippage)
    paper_orch.submit_paper_order("s1", "AAPL", 10, 0.0, "MARKET", "BUY", "rationales")

    # Start paper market data routing
    orchestrator.start_paper_market()

    # Emit a simulated live candle event through the Event Bus
    event = MarketDataReceived(
        source="gateway",
        payload={
            "symbol": "AAPL",
            "candle": {"close": 110.0, "volume": 50000.0, "symbol": "AAPL"}
        }
    )
    event_bus.publish(event)

    # Wait for dispatcher synchronizer callbacks
    assert orchestrator.cache.get_price("AAPL") == 110.0
    
    # Verify open positions and drawdown recalculations
    # Position unrealized return = 10 * (110 - 100.01) = 99.9
    pos = paper_orch.repository.get_position("AAPL")
    assert pos.unrealized_pnl == pytest.approx(99.9)

    orchestrator.stop_paper_market()
