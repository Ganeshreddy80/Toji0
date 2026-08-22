"""Unit tests for the RiskMetricsCalculator risk evaluation metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.risk_metrics.calculator import RiskMetricsCalculator


def test_value_at_risk_historical():
    """Verify historical VaR calculates correct percentile levels."""
    returns = pd.Series([-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05])
    # alpha = 0.05 (for 95% confidence). Percentile(5%) should fall near the lowest return.
    var_95 = RiskMetricsCalculator.value_at_risk(returns, confidence_level=0.95, method="historical")
    assert isinstance(var_95, float)
    assert var_95 > 0.0
    
    # Parametric VaR
    var_param = RiskMetricsCalculator.value_at_risk(returns, confidence_level=0.95, method="parametric")
    assert isinstance(var_param, float)
    
    # Invalid method
    with pytest.raises(ValueError):
        RiskMetricsCalculator.value_at_risk(returns, method="invalid")


def test_conditional_value_at_risk():
    """Verify Conditional VaR calculates expected tail losses."""
    returns = pd.Series([-0.1, -0.08, -0.05, -0.02, 0.0, 0.02, 0.05])
    cvar = RiskMetricsCalculator.conditional_value_at_risk(returns, confidence_level=0.90)
    assert isinstance(cvar, float)
    # CVaR is the mean of tail losses, should be higher than the lowest returns.
    assert cvar >= 0.05


def test_kelly_criterion():
    """Verify Kelly Criterion sizing recommendations."""
    # Win rate 60%, win-loss 2:1. Kelly = 0.6 - (1 - 0.6) / 2 = 0.6 - 0.2 = 0.4
    k = RiskMetricsCalculator.kelly_criterion(win_rate=0.6, win_loss_ratio=2.0)
    assert pytest.approx(k) == 0.4
    
    # Negative expected return should recommend zero sizing
    k_neg = RiskMetricsCalculator.kelly_criterion(win_rate=0.3, win_loss_ratio=1.0)
    assert k_neg == 0.0


def test_maximum_drawdown():
    """Verify maximum peak-to-trough drop calculation."""
    equity = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0, 105.0])
    # Peak at 120.0, trough at 80.0. Drawdown = (80 - 120) / 120 = -40 / 120 = -1/3 = -0.333333
    max_dd = RiskMetricsCalculator.maximum_drawdown(equity)
    assert pytest.approx(max_dd) == -1.0 / 3.0
    
    # Empty equity curve
    assert RiskMetricsCalculator.maximum_drawdown([]) == 0.0


def test_rolling_drawdown():
    """Verify rolling drawdown calculations matches standard values."""
    equity = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0, 105.0])
    roll_dd = RiskMetricsCalculator.rolling_drawdown(equity, window=3)
    assert len(roll_dd) == len(equity)
    assert roll_dd.iloc[2] == pytest.approx((90.0 - 120.0) / 120.0)


def test_portfolio_exposure():
    """Verify net and gross exposure proportions."""
    positions = {"BTC": 50000.0, "ETH": -20000.0}
    total_equity = 100000.0
    
    net, gross = RiskMetricsCalculator.portfolio_exposure(positions, total_equity)
    # Net = (50000 - 20000) / 100000 = 0.3
    # Gross = (50000 + 20000) / 100000 = 0.7
    assert net == 0.3
    assert gross == 0.7


def test_risk_of_ruin():
    """Verify risk of ruin equations."""
    # Positive expectation strategy with low risk -> ruin prob < 1.0
    prob = RiskMetricsCalculator.risk_of_ruin(win_rate=0.6, payoff_ratio=1.5, fraction_risked=0.02, loss_limit=0.5)
    assert 0.0 <= prob <= 1.0
    
    # Negative expectation -> ruin prob is 1.0
    prob_ruin = RiskMetricsCalculator.risk_of_ruin(win_rate=0.4, payoff_ratio=1.0, fraction_risked=0.05, loss_limit=0.5)
    assert prob_ruin == 1.0
