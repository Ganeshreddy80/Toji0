"""Unit and integration tests for the TOJI Institutional Market Regime Intelligence Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.market_regime.models import (
    RegimeType,
    VolatilityRegime,
    LiquidityRegime,
    MarketRegime
)
from research_platform.market_regime.orchestrator import MarketRegimeOrchestrator
from research_platform.market_regime.volatility import VolatilityDetector
from research_platform.market_regime.liquidity import LiquidityDetector
from research_platform.market_regime.trend import TrendDetector
from research_platform.market_regime.structure import MarketStructureAnalyzer

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
    return MarketRegimeOrchestrator(event_bus, container=container)


def test_volatility_detection():
    """Verify classification of volatility (LOW, NORMAL, HIGH) based on input prices/ATRs."""
    detector = VolatilityDetector()

    # 1. Low relative ATR
    prices_low = [100.0, 100.2, 100.1, 100.3, 100.2]
    atr_low = [0.5, 0.6, 0.5, 0.4, 0.5]  # ~0.5% rel ATR
    res_low = detector.detect_volatility(prices_low, atr_low)
    assert res_low == VolatilityRegime.LOW

    # 2. High relative ATR
    prices_high = [100.0, 105.0, 95.0, 110.0, 90.0]
    atr_high = [4.5, 5.0, 4.8, 5.2, 4.7]  # ~4.8% rel ATR
    res_high = detector.detect_volatility(prices_high, atr_high)
    assert res_high == VolatilityRegime.HIGH

    # 3. Normal relative ATR
    prices_norm = [100.0, 101.0, 100.5, 101.5, 100.8]
    atr_norm = [1.8, 2.0, 1.9, 2.1, 1.8]  # ~1.9% rel ATR
    res_norm = detector.detect_volatility(prices_norm, atr_norm)
    assert res_norm == VolatilityRegime.NORMAL


def test_liquidity_detection():
    """Verify classification of liquidity based on spreads and volumes."""
    detector = LiquidityDetector()

    # 1. Low spread -> HIGH liquidity
    spreads_high = [0.0005, 0.0008, 0.0006]
    res_high = detector.detect_liquidity([], spreads_high)
    assert res_high == LiquidityRegime.HIGH

    # 2. High spread -> LOW liquidity
    spreads_low = [0.006, 0.008, 0.007]
    res_low = detector.detect_liquidity([], spreads_low)
    assert res_low == LiquidityRegime.LOW

    # 3. Mid spread -> NORMAL liquidity
    spreads_norm = [0.002, 0.003, 0.0025]
    res_norm = detector.detect_liquidity([], spreads_norm)
    assert res_norm == LiquidityRegime.NORMAL


def test_trend_detection():
    """Verify trend classifications based on price lists."""
    detector = TrendDetector()

    # Bullish: last price high, slope positive
    prices_up = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    assert detector.detect_trend(prices_up) == RegimeType.BULLISH

    # Bearish: last price low, slope negative
    prices_down = [100.0, 99.0, 98.0, 97.0, 96.0, 95.0]
    assert detector.detect_trend(prices_down) == RegimeType.BEARISH

    # Rangebound: sideways consolidation
    prices_flat = [100.0, 100.5, 99.8, 100.2, 100.1, 99.9]
    assert detector.detect_trend(prices_flat) == RegimeType.RANGEBOUND


def test_market_structure_analysis():
    """Verify support/resistance pivots and breakout detections."""
    analyzer = MarketStructureAnalyzer()
    
    # Form pivots: local maximum at index 2 (value 110.0), local minimum at index 3 (value 90.0)
    prices = [100.0, 105.0, 110.0, 90.0, 95.0, 92.0, 94.0]
    
    struct = analyzer.analyze_structure(prices, prices, prices)
    assert 90.0 in struct.support_levels
    assert 110.0 in struct.resistance_levels


def test_transition_tracking_and_probabilities(orchestrator):
    """Verify regime change event tracking and dynamic transition probabilities calculation."""
    # Register multiple regimes to trigger transitions
    prices1 = [100.0, 100.5, 99.8, 100.2, 100.1, 99.9]  # Rangebound
    prices2 = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]  # Bullish
    
    r1 = orchestrator.analyze_regime("BTCUSD", prices1, [10000.0], [0.002], [1.5])
    assert r1.regime_type == RegimeType.RANGEBOUND

    # Analyze again to trigger transition
    r2 = orchestrator.analyze_regime("BTCUSD", prices2, [10000.0], [0.002], [1.5])
    assert r2.regime_type == RegimeType.BULLISH

    # Verify transition logged
    transitions = orchestrator.repository.list_transitions("BTCUSD")
    assert len(transitions) == 1
    assert transitions[0].old_regime.regime_type == RegimeType.RANGEBOUND
    assert transitions[0].new_regime.regime_type == RegimeType.BULLISH
    # First transition, probability is 1.0
    assert transitions[0].probability == 1.0


def test_orchestrator_subsystem_integration(orchestrator, container):
    """Verify orchestrator updates Event Bus, Institutional Memory, and Knowledge Graph."""
    prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    
    # Run analysis
    orchestrator.analyze_regime("BTCUSD", prices, [10000.0], [0.002], [1.5])

    # 1. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("market_regimes")
    assert len(mems) == 1
    assert mems[0].symbol == "BTCUSD"

    # 2. Verify Knowledge Graph nodes and links
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "BTCUSD" in node_ids
    # Should have a MARKET_REGIME node
    regime_nodes = [n for n in nodes if n.node_type == "MARKET_REGIME"]
    assert len(regime_nodes) == 1
    
    # Link uses: BTCUSD uses MARKET_REGIME
    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "uses" in edge_types
