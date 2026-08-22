"""Unit tests for the StatsCalculator performance statistics calculations."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from analytics.statistics.calculator import StatsCalculator


def test_calculate_cagr():
    """Verify CAGR compounds returns correctly."""
    # Constant daily return of 0.1% over 252 days (1 year)
    returns = pd.Series([0.001] * 252)
    cagr = StatsCalculator.calculate_cagr(returns, periods_per_year=252)
    expected = (1.001 ** 252) - 1.0
    assert pytest.approx(cagr, abs=1e-6) == expected
    
    # Depleted portfolio should return -1.0
    bankrupt_returns = pd.Series([-0.5, -0.5, -0.5])
    assert StatsCalculator.calculate_cagr(bankrupt_returns) == -1.0
    
    # Empty returns
    assert StatsCalculator.calculate_cagr(pd.Series(dtype=float)) == 0.0


def test_sharpe_ratio():
    """Verify Sharpe ratio calculations with positive and flat returns."""
    # Constant daily returns: standard deviation is 0.0 -> Sharpe should be 0.0
    returns_flat = pd.Series([0.001] * 50)
    assert StatsCalculator.sharpe_ratio(returns_flat) == 0.0
    
    # Sine wave returns
    returns = pd.Series([0.001, -0.001] * 126)  # Mean 0, std > 0
    assert StatsCalculator.sharpe_ratio(returns) == 0.0
    
    # Positive variance series
    returns_varying = pd.Series([0.002, 0.001, 0.003, -0.001, 0.002] * 50)
    sharpe = StatsCalculator.sharpe_ratio(returns_varying, risk_free_rate=0.01)
    assert isinstance(sharpe, float)


def test_sortino_ratio():
    """Verify Sortino ratio downside volatility scaling."""
    returns = pd.Series([0.01, -0.02, 0.015, -0.01, 0.03] * 50)
    sortino = StatsCalculator.sortino_ratio(returns, target_return=0.0)
    assert isinstance(sortino, float)
    
    # All positive returns -> no downside deviation -> should return 0.0
    all_positive = pd.Series([0.01] * 10)
    assert StatsCalculator.sortino_ratio(all_positive) == 0.0


def test_calmar_and_mar_ratio():
    """Verify Calmar and MAR ratio logic."""
    returns = pd.Series([0.001] * 252)
    calmar = StatsCalculator.calmar_ratio(returns, max_drawdown=-0.1)
    cagr = StatsCalculator.calculate_cagr(returns)
    assert calmar == cagr / 0.1
    
    mar = StatsCalculator.mar_ratio(returns, max_drawdown=-0.05)
    mean_ann = float(np.mean(returns) * 252)
    assert mar == mean_ann / 0.05
    
    # Max drawdown is 0
    assert StatsCalculator.calmar_ratio(returns, max_drawdown=0.0) == 0.0


def test_omega_ratio():
    """Verify Omega ratio gains vs losses calculation."""
    returns = pd.Series([0.01, -0.005, 0.02, -0.01])
    omega = StatsCalculator.omega_ratio(returns, threshold=0.0)
    assert omega == (0.01 + 0.02) / (0.005 + 0.01)
    
    # All gains
    all_positive = pd.Series([0.01, 0.02])
    assert StatsCalculator.omega_ratio(all_positive) == float("inf")


def test_profit_factor_and_expectancy():
    """Verify Profit Factor and Expectancy calculations."""
    trades = pd.Series([100.0, -50.0, 200.0, -100.0])
    pf = StatsCalculator.profit_factor(trades)
    assert pf == 300.0 / 150.0
    
    exp = StatsCalculator.expectancy(trades)
    assert exp == (0.5 * 150.0) - (0.5 * 75.0)  # win rate 0.5, avg win 150, loss rate 0.5, avg loss 75
    
    # Zero trades
    assert StatsCalculator.profit_factor(pd.Series(dtype=float)) == 0.0
    assert StatsCalculator.expectancy(pd.Series(dtype=float)) == 0.0


def test_recovery_factor_and_ulcer_index():
    """Verify Recovery Factor and Ulcer Index calculations."""
    assert StatsCalculator.recovery_factor(1000.0, -200.0) == 5.0
    assert StatsCalculator.recovery_factor(100.0, 0.0) == 0.0
    
    # Returns for Ulcer Index
    returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
    ui = StatsCalculator.ulcer_index(returns)
    assert isinstance(ui, float)
    assert ui >= 0.0


def test_alpha_beta():
    """Verify Alpha and Beta calculations against a benchmark."""
    returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.03])
    benchmark = pd.Series([0.008, -0.004, 0.015, -0.008, 0.02])
    
    alpha, beta = StatsCalculator.alpha_beta(returns, benchmark)
    assert isinstance(alpha, float)
    assert isinstance(beta, float)


def test_tracking_error_and_information_ratio():
    """Verify Tracking Error and Information Ratio calculations."""
    returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.03])
    benchmark = pd.Series([0.008, -0.004, 0.015, -0.008, 0.02])
    
    te = StatsCalculator.tracking_error(returns, benchmark)
    ir = StatsCalculator.information_ratio(returns, benchmark)
    
    assert te >= 0.0
    assert isinstance(ir, float)


def test_correlation_matrix():
    """Verify Pearson correlation calculation matrix."""
    df = pd.DataFrame({
        "A": [1.0, 2.0, 3.0, 4.0],
        "B": [2.0, 4.0, 6.0, 8.0],  # Perfectly correlated with A
    })
    corr = StatsCalculator.correlation_matrix(df)
    assert corr.loc["A", "B"] == pytest.approx(1.0)


def test_rolling_metrics():
    """Verify rolling Sharpe and rolling Beta calculation Series."""
    returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02, -0.03] * 10)
    benchmark = pd.Series([0.008, -0.015, 0.025, -0.008, 0.015, -0.025] * 10)
    
    r_sharpe = StatsCalculator.rolling_sharpe(returns, window=5)
    r_beta = StatsCalculator.rolling_beta(returns, benchmark, window=5)
    
    assert len(r_sharpe) == len(returns)
    assert len(r_beta) == len(returns)
    assert r_sharpe.iloc[0] == 0.0  # NaN fill checks
