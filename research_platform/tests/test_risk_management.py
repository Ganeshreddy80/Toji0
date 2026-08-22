"""Unit tests for the Risk Management System.
"""

from __future__ import annotations

import numpy as np
import pytest
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.risk_management.compliance import ComplianceEngine
from research_platform.risk_management.cvar import CVaREngine
from research_platform.risk_management.exposure import ExposureEngine
from research_platform.risk_management.leverage import LeverageEngine
from research_platform.risk_management.limits import RiskLimitsEngine
from research_platform.risk_management.liquidity import LiquidityRiskEngine
from research_platform.risk_management.market_risk import MarketRiskEvaluator
from research_platform.risk_management.models import RiskLimits, StressScenario
from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
from research_platform.risk_management.position_risk import PositionRiskEvaluator
from research_platform.risk_management.portfolio_risk import PortfolioRiskEvaluator
from research_platform.risk_management.scenario import StressScenarios
from research_platform.risk_management.stress_testing import StressTestingEngine
from research_platform.risk_management.var import VaREngine
from research_platform.risk_management.kill_switch import KillSwitch
from research_platform.oms.models import OrderRequest


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return RiskManagementOrchestrator(event_bus)


def test_position_risk_evaluations():
    """Verify position sizing rewards and stop distances."""
    evaluator = PositionRiskEvaluator()
    req = OrderRequest(order_id="o1", symbol="BTC/USDT", direction="BUY", quantity=1.0, order_type="LIMIT", price=50000.0)
    
    res = evaluator.evaluate_position_risk(req)
    assert res.symbol == "BTC/USDT"
    # Stop distance at 5% is 2500.0
    assert res.stop_loss_distance == 2500.0


def test_portfolio_exposure_metrics():
    """Verify gross and net exposure calculations."""
    evaluator = PortfolioRiskEvaluator()
    weights = {"BTC": 0.4, "ETH": -0.2}

    res = evaluator.calculate_portfolio_risk(weights)
    assert res.gross_exposure == pytest.approx(0.6)
    assert res.net_exposure == pytest.approx(0.2)


def test_parametric_and_historical_var():
    """Verify parametric VaR and historical percentile boundaries."""
    engine = VaREngine(confidence_level=0.95)
    returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02, -0.04, 0.05])

    res = engine.calculate_var(returns, portfolio_value=100000.0)
    assert res.parametric_var > 0.0
    assert res.historical_var > 0.0
    assert res.confidence_level == 0.95


def test_expected_shortfall_cvar():
    """Verify expected shortfall tail return averages."""
    engine = CVaREngine(confidence_level=0.95)
    returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02, -0.04, 0.05])

    res = engine.calculate_cvar(returns, portfolio_value=100000.0)
    assert res.expected_shortfall > 0.0
    assert res.confidence_level == 0.95


def test_stress_testing_scenarios():
    """Verify expected loss multiplier under Flash Crash scenario."""
    engine = StressTestingEngine(loss_limit=20000.0)
    returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])

    res = engine.run_stress_test(returns, StressScenarios.FLASH_CRASH, portfolio_value=100000.0)
    assert res.scenario_name == "Flash Crash"
    assert res.expected_loss > 0.0


def test_compliance_and_kill_switches():
    """Verify compliance engine rejects orders when kill switch is active."""
    limits = RiskLimitsEngine()
    kill = KillSwitch()
    compliance = ComplianceEngine(limits, kill)

    req = OrderRequest(order_id="o1", symbol="BTC/USDT", direction="BUY", quantity=1.0, order_type="LIMIT", price=50000.0)

    # 1. Normal state -> compliant
    c1 = compliance.evaluate_compliance(req)
    assert c1.compliant is True

    # 2. Kill switch active -> rejected
    kill.activate("Emergency Halt")
    c2 = compliance.evaluate_compliance(req)
    assert c2.compliant is False
    assert any("Kill Switch" in r for r in c2.rejection_reasons)


def test_risk_orchestrator(orchestrator):
    """Verify orchestrator runs pipelines and publishes events."""
    req = OrderRequest(
        order_id="ord_777",
        symbol="BTC/USDT",
        direction="BUY",
        quantity=1.0,
        order_type="LIMIT",
        price=50000.0
    )
    returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    weights = {"BTC": 0.5}

    res = orchestrator.validate_order(req, returns, weights)
    assert res.approval.approved is True
    assert len(orchestrator.repository.list_alerts()) == 0
