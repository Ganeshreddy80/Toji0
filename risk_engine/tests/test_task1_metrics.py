"""Unit tests for Sprint 1 Task 1: Removing fabricated performance metrics from Risk Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from portfolio_engine.core.models import ClosedPosition, PortfolioSnapshot, PortfolioMetrics
from portfolio_engine.core.enums import PositionSide
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.models import RiskMetrics, RiskConfiguration, AccountRisk
from risk_engine.core.orchestrator import RiskOrchestrator
from risk_engine.analysis.rules_engine import RiskRulesEngine
from risk_engine.analysis.drawdown_engine import DrawdownEngine


class DummyClosedPosition:
    """Mock closed position for testing performance metric aggregation."""
    def __init__(self, realized_pnl: float) -> None:
        self.realized_pnl = realized_pnl


def test_valid_history_metrics():
    """Verify empirical metric calculation when valid returns and closed trades exist."""
    closed = [
        DummyClosedPosition(realized_pnl=100.0),
        DummyClosedPosition(realized_pnl=-50.0),
        DummyClosedPosition(realized_pnl=200.0),
        DummyClosedPosition(realized_pnl=150.0),
    ]
    returns = [0.01, -0.005, 0.02, 0.015]

    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=400.0,
        initial_balance=10000.0,
        max_drawdown=0.05,
        closed_positions=closed,
        returns_history=returns,
    )

    # Win rate: 3 wins / 4 trades = 0.75
    assert metrics.win_rate == 0.75
    # Gross profit = 450, gross loss = 50 -> profit factor = 9.0 (dimensionless ratio)
    assert metrics.profit_factor == 9.0
    # Expectancy = 400 / 4 = 100.0
    assert metrics.expectancy == 100.0
    # Sharpe & Sortino: sample std dev convention (n-1), annualized by sqrt(252), MAR=0
    assert metrics.sharpe_ratio > 0.0
    assert metrics.sortino_ratio > 0.0
    # Calmar ratio = (400 / 10000) / 0.05 = 0.04 / 0.05 = 0.8
    assert metrics.calmar_ratio == 0.8


def test_empty_history_metrics():
    """Verify metrics default to 0.0 without fabricating fake numbers when history is empty."""
    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=0.0,
        initial_balance=10000.0,
        max_drawdown=0.0,
        closed_positions=[],
        returns_history=[],
    )

    assert metrics.sharpe_ratio == 0.0
    assert metrics.sortino_ratio == 0.0
    assert metrics.calmar_ratio == 0.0
    assert metrics.profit_factor == 0.0
    assert metrics.win_rate == 0.0
    assert metrics.expectancy == 0.0


def test_insufficient_history_metrics():
    """Verify Sharpe and Sortino ratios remain 0.0 when less than 2 return data points exist."""
    closed = [DummyClosedPosition(realized_pnl=500.0)]
    returns = [0.05]  # Only 1 return point -> sample variance undefined

    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=500.0,
        initial_balance=10000.0,
        max_drawdown=0.02,
        closed_positions=closed,
        returns_history=returns,
    )

    # Sharpe and Sortino cannot be calculated from 1 point
    assert metrics.sharpe_ratio == 0.0
    assert metrics.sortino_ratio == 0.0

    # Trade-level statistics from 1 trade
    assert metrics.win_rate == 1.0
    assert metrics.expectancy == 500.0


def test_invalid_history_metrics():
    """Verify metrics return 0.0 and rules engine fails closed when account parameters are invalid/uninitialized."""
    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=500.0,
        initial_balance=0.0,  # Invalid balance
        max_drawdown=0.0,
        closed_positions=[],
        returns_history=[],
    )

    assert metrics.sharpe_ratio == 0.0
    assert metrics.win_rate == 0.0

    # Test RulesEngine fail-closed behavior on non-positive balance/equity
    from risk_engine.core.models import (
        PortfolioRisk, ExposureRisk, DrawdownRisk, MarginRisk, LeverageRisk, CircuitBreakerState
    )

    rules_engine = RiskRulesEngine()
    invalid_account = AccountRisk(balance=0.0, equity=0.0, initial_balance=0.0)

    state = rules_engine.evaluate_request(
        symbol="BTCUSDT",
        timeframe="1m",
        quantity=1.0,
        price=100.0,
        leverage=1.0,
        margin_required=0.0,
        account_risk=invalid_account,
        portfolio_risk=PortfolioRisk(gross_exposure=0.0, net_exposure=0.0, open_positions_count=0),
        exposure_risk=ExposureRisk(symbol_exposure={}, sector_exposure={}),
        drawdown_risk=DrawdownRisk(rolling_drawdown=0.0, max_drawdown=0.0),
        margin_risk=MarginRisk(margin_usage_pct=0.0),
        leverage_risk=LeverageRisk(account_leverage=1.0, max_leverage_limit=5.0),
        circuit_breaker=CircuitBreakerState(halt_trading=False),
        metrics=metrics,
        config=RiskConfiguration(),
    )

    assert state.assessment.decision == RiskDecision.BLOCK
    assert any(v.rule_id == "RE_ACC_001" for v in state.assessment.violations)


def test_regression_no_fabricated_metrics():
    """Verify that no fabricated metrics (e.g. fake Sharpe ratio formula) are returned for pnl without return history."""
    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=1000.0,
        initial_balance=100000.0,
        max_drawdown=0.0,
        closed_positions=[],
        returns_history=[],
    )

    # In the old code, sharpe_ratio was fabricated as round(pnl / (initial_balance * 0.1), 2) = 0.1
    # win_rate was fabricated as 0.5 + pnl / (2 * initial_balance) = 0.505
    # Verify these fabricated values NO LONGER exist!
    assert metrics.sharpe_ratio == 0.0
    assert metrics.sortino_ratio == 0.0
    assert metrics.win_rate == 0.0
    assert metrics.expectancy == 0.0


def test_drawdown_time_under_water_no_fake_fallback():
    """Verify DrawdownEngine does not fallback to hardcoded 60.0 seconds when historical timestamps are missing."""
    engine = DrawdownEngine()
    model, alert, halt = engine.calculate_drawdown(
        current_equity=9000.0,
        peak_equity=10000.0,
        net_profit=-1000.0,
    )

    # In old code, model.time_under_water was hardcoded to 60.0
    assert model.time_under_water == 0.0


def test_profit_factor_no_losses_is_zero():
    """Verify profit_factor is 0.0 (undefined, not a dollar amount) when all trades are wins."""
    all_winners = [
        DummyClosedPosition(realized_pnl=100.0),
        DummyClosedPosition(realized_pnl=200.0),
        DummyClosedPosition(realized_pnl=50.0),
    ]

    metrics = RiskOrchestrator._calculate_empirical_metrics(
        net_profit=350.0,
        initial_balance=10000.0,
        max_drawdown=0.0,
        closed_positions=all_winners,
        returns_history=[0.01, 0.02, 0.005],  # 3 points -> enough for Sharpe/Sortino
    )

    # profit_factor is undefined (no losses to divide by) — must be 0.0, not a dollar amount
    assert metrics.profit_factor == 0.0
    assert metrics.win_rate == 1.0


def test_p0_fail_closed_no_financial_state():
    """Verify process_execution_request blocks immediately when no portfolio state or financial payload exists."""
    from risk_engine.core.orchestrator import RiskOrchestrator
    from risk_engine.core.enums import RiskDecision
    from risk_engine.core.state import RiskStateStore
    from risk_engine.core.repository import RiskRepository
    from risk_engine.analysis.risk_engine import RiskEngine

    orchestrator = RiskOrchestrator()
    orchestrator.initialize(
        state_store=RiskStateStore(),
        repository=RiskRepository(),
        risk_engine=RiskEngine(),
        # No container — no PortfolioStateStore will be resolved
    )

    # Payload with no financial state fields
    payload = {"symbol": "BTCUSDT", "timeframe": "1m", "quantity": 1.0, "price": 50000.0}
    result = orchestrator.process_execution_request(payload)

    assert result.assessment.decision == RiskDecision.BLOCK
    assert any(v.rule_id == "RE_STATE_001" for v in result.assessment.violations)
