"""Unit tests for the Portfolio Construction & Risk Engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.portfolio_engine.allocator import PortfolioAllocator
from research_platform.portfolio_engine.constraints import ConstraintEngine
from research_platform.portfolio_engine.covariance import CovarianceEngine
from research_platform.portfolio_engine.factor_model import FactorModel
from research_platform.portfolio_engine.forecast import ForecastEngine
from research_platform.portfolio_engine.models import (
    PortfolioConfiguration,
    PortfolioWeights,
    RiskBudget
)
from research_platform.portfolio_engine.optimizer import PortfolioOptimizer
from research_platform.portfolio_engine.orchestrator import PortfolioEngineOrchestrator
from research_platform.portfolio_engine.performance import BrinsonAttribution
from research_platform.portfolio_engine.rebalancer import PortfolioRebalancer
from research_platform.portfolio_engine.risk_budget import PortfolioRiskBudget


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return PortfolioEngineOrchestrator(event_bus)


def test_covariance_estimators():
    """Verify rolling and Ledoit-Wolf shrinkage covariance matrices."""
    returns = pd.DataFrame({
        "BTC": [0.01, -0.02, 0.03, -0.01, 0.02],
        "ETH": [0.02, -0.01, 0.04, -0.02, 0.01]
    })

    # Rolling
    engine_roll = CovarianceEngine(method="rolling")
    cov_roll = engine_roll.calculate_covariance(returns)
    assert len(cov_roll.matrix) == 2
    assert cov_roll.matrix[0][0] > 0.0

    # Shrinkage
    engine_shrink = CovarianceEngine(method="shrinkage")
    cov_shrink = engine_shrink.calculate_covariance(returns)
    assert len(cov_shrink.matrix) == 2
    assert cov_shrink.matrix[0][1] == pytest.approx(cov_roll.matrix[0][1] * 0.8 + 0.2 * cov_roll.matrix[0][1])


def test_forecast_returns():
    """Verify historical mean and momentum return forecasts."""
    prices = pd.DataFrame({
        "BTC": [100.0, 101.0, 102.0, 101.0, 103.0],
        "ETH": [200.0, 202.0, 204.0, 202.0, 206.0]
    })

    forecaster = ForecastEngine(method="momentum", window=4)
    res = forecaster.forecast_returns(prices)
    # momentum cumulative return BTC: 103 / 100 - 1 = 3%
    assert res.forecasts["BTC"] > 0.0


def test_portfolio_allocator():
    """Verify Equal Weight and Inverse Volatility allocations."""
    returns = pd.DataFrame({
        "BTC": [0.01, -0.02, 0.03],
        "ETH": [0.05, -0.08, 0.09]  # higher variance
    })

    # Equal
    alloc_eq = PortfolioAllocator(method="equal")
    res_eq = alloc_eq.allocate(["BTC", "ETH"], returns)
    assert res_eq.weights.weights["BTC"] == 0.5

    # Inverse Vol
    alloc_vol = PortfolioAllocator(method="inverse_vol")
    res_vol = alloc_vol.allocate(["BTC", "ETH"], returns)
    # BTC should have higher weight because it has lower variance
    assert res_vol.weights.weights["BTC"] > res_vol.weights.weights["ETH"]


def test_optimizer_mvo_and_hrp():
    """Verify Mean Variance and HRP weight distributions."""
    forecast = ForecastEngine(method="mean")
    cov_engine = CovarianceEngine(method="rolling")

    prices = pd.DataFrame({
        "BTC": [10.0, 10.2, 10.1, 10.3],
        "ETH": [20.0, 20.4, 20.2, 20.6]
    })
    
    returns = prices.pct_change().dropna()
    fc = forecast.forecast_returns(prices)
    cov = cov_engine.calculate_covariance(returns)

    optimizer = PortfolioOptimizer(optimizer_name="max_sharpe")
    res = optimizer.optimize(["BTC", "ETH"], fc, cov)
    assert sum(res.weights.weights.values()) == pytest.approx(1.0)

    # HRP
    optimizer_hrp = PortfolioOptimizer(optimizer_name="hrp")
    res_hrp = optimizer_hrp.optimize(["BTC", "ETH"], fc, cov)
    assert sum(res_hrp.weights.weights.values()) == pytest.approx(1.0)


def test_factor_exposures():
    """Verify portfolio style factor load evaluations."""
    returns = pd.DataFrame({
        "BTC": [0.01, 0.02, 0.03, 0.01, 0.02],
        "ETH": [0.02, 0.03, 0.04, 0.02, 0.03]
    })
    weights = PortfolioWeights(weights={"BTC": 0.6, "ETH": 0.4}, timestamp=datetime.now(timezone.utc))

    model = FactorModel()
    res = model.calculate_exposures(weights, returns)
    assert res.factor_loadings["market"] > 0.0


def test_risk_budget_contributions():
    """Verify portfolio VaR, CVaR, and component contributions."""
    weights = PortfolioWeights(weights={"BTC": 0.6, "ETH": 0.4}, timestamp=datetime.now(timezone.utc))
    cov = CovarianceEngine().calculate_covariance(
        pd.DataFrame({
            "BTC": [0.01, -0.02, 0.03],
            "ETH": [0.02, -0.01, 0.04]
        })
    )

    budget = PortfolioRiskBudget()
    res = budget.calculate_risk_contributions(weights, cov)
    assert "BTC" in res.percentage_contribution
    assert sum(res.percentage_contribution.values()) == pytest.approx(1.0)

    # VaR/CVaR
    var, cvar = PortfolioRiskBudget.calculate_var_cvar(weights, cov)
    assert var > 0.0
    assert cvar >= var


def test_constraint_engine():
    """Verify weight limit and leverage constraint violations."""
    weights = PortfolioWeights(weights={"BTC": 0.8, "ETH": 0.9}, timestamp=datetime.now(timezone.utc))
    # Max weight 30%, leverage 1.5
    engine = ConstraintEngine(max_weight=0.30, max_leverage=1.50)
    violations = engine.check_constraints(weights)
    assert len(violations) > 0
    assert any(v.constraint_name == "MaxWeight" for v in violations)
    assert any(v.constraint_name == "MaxLeverage" for v in violations)


def test_rebalancer_triggers():
    """Verify drift threshold rebalance scheduling."""
    current = PortfolioWeights(weights={"BTC": 0.5, "ETH": 0.5}, timestamp=datetime.now(timezone.utc))
    target = PortfolioWeights(weights={"BTC": 0.6, "ETH": 0.4}, timestamp=datetime.now(timezone.utc))

    rebalancer = PortfolioRebalancer(drift_threshold=0.05)
    plan = rebalancer.evaluate_rebalance(current, target)
    assert plan is not None
    assert plan.trades_needed["BTC"] == pytest.approx(0.1)


def test_brinson_attribution():
    """Verify Brinson attribution selection and allocation effects."""
    p_weights = PortfolioWeights(weights={"BTC": 0.6, "ETH": 0.4}, timestamp=datetime.now(timezone.utc))
    b_weights = PortfolioWeights(weights={"BTC": 0.5, "ETH": 0.5}, timestamp=datetime.now(timezone.utc))
    
    p_ret = {"BTC": 0.10, "ETH": 0.05}
    b_ret = {"BTC": 0.08, "ETH": 0.04}

    attribution = BrinsonAttribution()
    res = attribution.calculate_attribution(p_weights, b_weights, p_ret, b_ret)
    assert "BTC" in res.allocation_effect
    assert "BTC" in res.selection_effect
    assert res.total_attribution > 0.0


def test_portfolio_orchestrator(orchestrator):
    """Verify returns forecasting, covariances MVO sequence construction."""
    prices = pd.DataFrame({
        "BTC": [100.0, 102.0, 101.0, 103.0, 102.0],
        "ETH": [200.0, 204.0, 202.0, 206.0, 204.0]
    })

    config = PortfolioConfiguration(
        portfolio_id="port_123",
        optimizer_type="MAX_SHARPE",
        forecast_type="MEAN",
        risk_budget=RiskBudget(target_contributions={"BTC": 0.5, "ETH": 0.5})
    )

    weights = orchestrator.construct_portfolio(config, prices)
    assert "BTC" in weights.weights
    assert sum(weights.weights.values()) == pytest.approx(1.0)
    assert orchestrator.repository.get_portfolio("port_123") is not None
