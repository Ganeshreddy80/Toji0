"""Unit tests verifying all 8 Sprint 4 Architectural Invariants for Portfolio Construction."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from portfolio_construction.core.enums import OptimizationObjective, PortfolioDecision
from portfolio_construction.core.models import (
    PortfolioCandidate,
    PortfolioConstraintConfig,
    TargetAllocation,
    TargetPortfolio,
)
from portfolio_construction.analysis.construction_engine import PortfolioConstructionEngine
from portfolio_construction.core.orchestrator import PortfolioConstructionOrchestrator
from portfolio_construction.core.state import PortfolioConstructionStateStore
from portfolio_construction.core.repository import PortfolioConstructionRepository
from strategy.core.models import StrategySignal
from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType


# ===========================================================================
# Invariant 1: Never Submit Orders
# ===========================================================================

def test_invariant_never_submit_orders():
    """Verify that portfolio construction models and engines contain zero order/broker submission methods or fields."""
    import portfolio_construction.core.models as mod_models
    import portfolio_construction.analysis.construction_engine as mod_eng
    import portfolio_construction.core.orchestrator as mod_orch

    field_names = set(TargetPortfolio.model_fields.keys())
    forbidden_order_fields = {"submit_order", "order_id", "broker", "oms", "execute_trade", "limit_price"}
    assert field_names.isdisjoint(forbidden_order_fields)

    for mod in (mod_models, mod_eng, mod_orch):
        assert not hasattr(mod, "submit_order")
        assert not hasattr(mod, "execute_order")


# ===========================================================================
# Invariant 2: Never Perform Position Sizing
# ===========================================================================

def test_invariant_never_perform_position_sizing():
    """Verify that portfolio outputs contain normalized allocation target weights [0.0, 1.0], NOT position sizing."""
    field_names = set(TargetAllocation.model_fields.keys())
    forbidden_sizing_fields = {
        "quantity", "lots", "dollar_amount", "leverage", "margin_required",
        "stop_loss_price", "take_profit_price"
    }
    assert field_names.isdisjoint(forbidden_sizing_fields)


# ===========================================================================
# Invariant 3: Never Bypass Risk Engine
# ===========================================================================

def test_invariant_never_bypass_risk_engine():
    """Verify that orchestrator publishes PortfolioConstructionApproved events to EventBus for downstream risk validation."""
    mock_event_bus = MagicMock()
    orch = PortfolioConstructionOrchestrator()
    orch.initialize(
        engine=PortfolioConstructionEngine(),
        state_store=PortfolioConstructionStateStore(),
        repository=PortfolioConstructionRepository(),
        event_bus=mock_event_bus,
    )

    sig = StrategySignal(
        signal_id="sig-001",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.85,
        confluence_score=80.0,
        reasoning="Valid buy signal",
    )

    state = orch.process_signals([sig])
    assert state.active_portfolio.decision == PortfolioDecision.REBALANCE

    pub_events = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "PortfolioConstructionApproved" in pub_events


# ===========================================================================
# Invariant 4: Portfolio Decisions Must Be Immutable
# ===========================================================================

def test_invariant_portfolio_decisions_immutable():
    """Verify TargetPortfolio is a frozen Pydantic model."""
    target = TargetPortfolio(
        decision=PortfolioDecision.HOLD,
        allocations={},
        target_weights={},
        total_weight=0.0,
        reasoning="Test hold",
    )
    with pytest.raises(Exception):
        target.total_weight = 0.50


# ===========================================================================
# Invariant 5: Invalid Candidate Sets Fail Closed to Empty Portfolio
# ===========================================================================

def test_invariant_invalid_candidate_sets_fail_closed():
    """Verify empty/None candidate set returns HOLD posture with target_weights={} and 0.0 confidence."""
    engine = PortfolioConstructionEngine()

    # Null/empty candidates
    p1 = engine.construct_portfolio([])
    assert p1.decision == PortfolioDecision.HOLD
    assert p1.target_weights == {}
    assert p1.confidence == 0.0

    p2 = engine.construct_portfolio(None)
    assert p2.decision == PortfolioDecision.HOLD
    assert p2.target_weights == {}


# ===========================================================================
# Invariant 6: Optimizer Failures Must Be Isolated
# ===========================================================================

def test_invariant_optimizer_failures_isolated():
    """Verify that an optimizer exception falls back gracefully to safe allocation or fail-closed HOLD."""
    mock_optimizer = MagicMock()
    mock_optimizer.optimize.side_effect = RuntimeError("Solver crash in optimizer")

    engine = PortfolioConstructionEngine(optimizer=mock_optimizer)
    c1 = PortfolioCandidate(
        signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Trend Following", confidence=0.80
    )

    # Engine catches optimizer crash and fails closed gracefully
    p = engine.construct_portfolio([c1])
    assert p.decision == PortfolioDecision.HOLD
    assert p.target_weights == {}
    assert "Fail-Closed" in p.reasoning


# ===========================================================================
# Invariant 7: Deterministic Outputs for Identical Inputs
# ===========================================================================

def test_invariant_deterministic_outputs():
    """Verify identical inputs yield 100% identical target portfolio outputs."""
    engine = PortfolioConstructionEngine()
    c1 = PortfolioCandidate(
        signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Trend Following", confidence=0.80
    )
    c2 = PortfolioCandidate(
        signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Breakout", confidence=0.75
    )

    p1 = engine.construct_portfolio([c1, c2])
    p2 = engine.construct_portfolio([c1, c2])

    assert p1.decision == p2.decision
    assert p1.target_weights == p2.target_weights
    assert p1.total_weight == p2.total_weight


# ===========================================================================
# Invariant 8: Constraint Violations Must Never Produce Approved Portfolios
# ===========================================================================

def test_invariant_constraint_violations_never_approved():
    """Verify that if constraint validation fails, decision is HOLD and no approved portfolio is produced."""
    mock_constraint_engine = MagicMock()
    mock_constraint_engine.validate_constraints.return_value = (False, ["Max sector exposure exceeded"])

    engine = PortfolioConstructionEngine(constraint_engine=mock_constraint_engine)
    c1 = PortfolioCandidate(
        signal_id="s1", symbol="SOL/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Momentum", confidence=0.85
    )

    portfolio = engine.construct_portfolio([c1])
    assert portfolio.decision == PortfolioDecision.HOLD
    assert portfolio.target_weights == {}
    assert "Constraint violations" in portfolio.reasoning
