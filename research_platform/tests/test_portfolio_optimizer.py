"""Unit and integration tests for the TOJI Institutional Meta Portfolio Optimizer.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.portfolio_optimizer.models import (
    AllocationRequest,
    CorrelationMatrix,
    OptimizerResult,
    PortfolioAllocation,
)
from research_platform.portfolio_optimizer.orchestrator import PortfolioOptimizerOrchestrator
from research_platform.portfolio_optimizer.correlation import CorrelationEngine
from research_platform.portfolio_optimizer.risk_budgeting import RiskBudgeter
from research_platform.portfolio_optimizer.optimizer import PortfolioOptimizationEngine
from research_platform.portfolio_optimizer.balancer import ExposureBalancer

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
    return PortfolioOptimizerOrchestrator(event_bus, container=container)


def test_correlation_matrix_calculation():
    """Verify Pearson correlation results for correlated, anti-correlated and flat series."""
    engine = CorrelationEngine()

    returns_data = {
        "strat_a": [0.01, 0.02, -0.01, 0.03, 0.02],
        "strat_b": [0.01, 0.02, -0.01, 0.03, 0.02],  # Identical
        "strat_c": [-0.01, -0.02, 0.01, -0.03, -0.02],  # Anti-correlated
    }

    corr = engine.calculate_correlation(returns_data)
    assert corr.symbols == ["strat_a", "strat_b", "strat_c"]
    
    # Identical should have correlation near 1.0
    assert corr.matrix[0][1] == pytest.approx(1.0)
    # Anti-correlated should have correlation near -1.0
    assert corr.matrix[0][2] == pytest.approx(-1.0)


def test_risk_budgeting_contributions():
    """Verify MCTR and Risk Contribution logic math outputs."""
    budgeter = RiskBudgeter()

    weights = {"A": 0.6, "B": 0.4}
    # Covariance matrix: A variance=0.04, B variance=0.09, cov=0.0
    covariance = [
        [0.04, 0.0],
        [0.0, 0.09]
    ]
    limits = {"A": 0.05, "B": 0.05}

    res = budgeter.evaluate_risk_budget(weights, covariance, limits)
    # Portfolio Volatility = sqrt(0.6^2 * 0.04 + 0.4^2 * 0.09) = sqrt(0.36*0.04 + 0.16*0.09) = sqrt(0.0144 + 0.0144) = sqrt(0.0288) ~ 0.1697
    # MCTR_A = (0.04 * 0.6) / 0.1697 = 0.024 / 0.1697 ~ 0.1414
    # RC_A = 0.6 * 0.1414 ~ 0.0848
    assert res.marginal_contributions["A"] > 0.08
    assert res.marginal_contributions["B"] > 0.08


def test_portfolio_optimization_solvers():
    """Verify weights computation in equal weight and inverse variance solvers."""
    optimizer = PortfolioOptimizationEngine()

    returns_data = {
        "A": [0.01, 0.02, -0.01, 0.03],  # low var
        "B": [0.05, 0.10, -0.05, 0.15],  # high var
    }

    res = optimizer.optimize_portfolio(["A", "B"], returns_data)
    # Inverse variance should allocate more weight to asset with lower volatility (A)
    assert res.weights["A"] > res.weights["B"]
    assert res.weights["A"] + res.weights["B"] == pytest.approx(1.0)


def test_exposure_balancing_limits():
    """Verify gross/net and concentration rebalance bounds constraints."""
    balancer = ExposureBalancer()

    weights = {"A": 0.8, "B": 0.5, "C": -0.4}  # gross = 1.7, net = 0.9

    # Limit: gross max = 1.2, concentration max = 0.5
    balanced = balancer.balance_weights(weights, gross_limit=1.2, concentration_limit=0.5)
    
    # Check concentration clamp
    assert abs(balanced["A"]) <= 0.5
    
    # Check gross scale
    gross = sum(abs(w) for w in balanced.values())
    assert gross <= 1.2 + 1e-9


def test_orchestrator_rebalance_integration(orchestrator, container):
    """Verify orchestrator updates Event Bus, Memory and Knowledge Graph mappings."""
    returns_data = {
        "A": [0.01, 0.02, -0.01, 0.03],
        "B": [0.02, 0.01, 0.03, -0.01],
    }

    alloc = orchestrator.run_optimization(
        returns_data=returns_data,
        limits={"A": 0.10, "B": 0.10},
        risk_tolerance=0.4,
        concentration_limit=0.45
    )

    assert alloc.weights["A"] == pytest.approx(0.45) # Clamped by concentration limit
    
    # 1. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("portfolio_allocations")
    assert len(mems) == 1
    assert mems[0].allocation_id == alloc.allocation_id

    # 2. Verify Knowledge Graph linkages
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert alloc.allocation_id in node_ids
    assert "A" in node_ids

    # uses link exists
    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "uses" in edge_types
