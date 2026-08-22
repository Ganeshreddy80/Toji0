"""Unit and integration tests for the TOJI Institutional Digital Twin & Simulation Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.simulation.models import (
    ReplayMode,
    SimOrder,
    SimTick,
    StressParameters,
)
from research_platform.simulation.orchestrator import SimulationOrchestrator
from research_platform.simulation.replayer import MarketReplayer
from research_platform.simulation.exchange import ExchangeSimulator

# Integration components
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

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return SimulationOrchestrator(event_bus, container=container)


def test_replayer_volatility_scaling():
    """Verify replayer scales price deviations under stress configurations."""
    replayer = MarketReplayer()

    ticks = [
        SimTick(price=100.0, volume=1000.0),
        SimTick(price=102.0, volume=1000.0),  # dev = 2.0
    ]

    # Volatility scaled by 2.0x -> replayed second tick price becomes 104.0
    config = ReplayConfigurationMock(vol_mult=2.0)
    stressed = replayer.replay_ticks(ticks, config)
    assert stressed[0].price == 100.0
    assert stressed[1].price == 104.0


def test_exchange_order_matching_fills():
    """Verify MARKET and LIMIT order matches execution logics on exchange."""
    exchange = ExchangeSimulator()

    # 1. MARKET BUY fills immediately with half-spread slippage
    # Tick price = 100.0, spread = 0.02. Ask is 100.01
    tick = SimTick(price=100.0, volume=1000.0, spread=0.02)
    order_mkt = SimOrder(order_id="o1", strategy_id="s1", symbol="BTCUSD", quantity=1.0, price=0.0, order_type="MARKET", side="BUY")
    
    filled_mkt = exchange.match_order(order_mkt, tick)
    assert filled_mkt.status == "FILLED"
    assert filled_mkt.price == pytest.approx(100.01)

    # 2. LIMIT BUY remains PENDING if ask is above limit price
    # Limit BUY at 99.0, Ask is 100.01 -> remains PENDING
    order_lmt = SimOrder(order_id="o2", strategy_id="s1", symbol="BTCUSD", quantity=1.0, price=99.0, order_type="LIMIT", side="BUY")
    pending = exchange.match_order(order_lmt, tick)
    assert pending.status == "PENDING"

    # LIMIT BUY fills if limit price covers ask price (e.g. limit is 101.0, Ask is 100.01)
    order_lmt_fill = SimOrder(order_id="o3", strategy_id="s1", symbol="BTCUSD", quantity=1.0, price=101.0, order_type="LIMIT", side="BUY")
    filled_lmt = exchange.match_order(order_lmt_fill, tick)
    assert filled_lmt.status == "FILLED"


def test_returns_replication_variance_error():
    """Verify math calculation of return mean squared replication error variance."""
    replayer = MarketReplayer()

    act = [0.01, 0.02, -0.01]
    sim = [0.012, 0.018, -0.009]
    # diffs = [0.002, -0.002, 0.001]
    # squared diffs = [0.000004, 0.000004, 0.000001] -> sum = 0.000009 -> MSE = 0.000003

    err = replayer.calculate_replication_error(act, sim)
    assert err == pytest.approx(0.000003)


def test_orchestrator_digital_twin_replays(orchestrator, container):
    """Verify orchestrator runs replays, updates Event Bus, memory logging, and graph mappings."""
    ticks = [
        SimTick(price=100.0, volume=1000.0, spread=0.02),
        SimTick(price=102.0, volume=1000.0, spread=0.02)
    ]
    orders = [
        SimOrder(order_id="order-1", strategy_id="strat-alpha", symbol="BTCUSD", quantity=10.0, price=0.0, order_type="MARKET", side="BUY")
    ]

    result = orchestrator.execute_simulation_replay(
        session_id="sim-run-123",
        strategy_ids=["strat-alpha"],
        mode=ReplayMode.MARKET,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        ticks=ticks,
        orders=orders,
        stress_params=StressParameters(volatility_multiplier=1.2),
        actual_returns=[0.02]
    )

    assert result.total_trades == 1
    assert result.replication_error > 0.0

    # 1. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("simulation_results")
    assert len(mems) == 1
    assert mems[0].session_id == "sim-run-123"

    # 2. Verify Knowledge Graph
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "sim-run-123" in node_ids
    assert "strat-alpha" in node_ids


class ReplayConfigurationMock:
    """Mock configuration containing stress parameters."""
    def __init__(self, vol_mult: float) -> None:
        self.stress_params = StressParameters(volatility_multiplier=vol_mult)
