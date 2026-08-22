"""Unit tests for the ReportGenerator quantitative summaries compiler."""

from __future__ import annotations

import pandas as pd
import pytest

from analytics.backtesting.runner import StrategyRunner
from analytics.reports.generator import ReportGenerator


def test_generate_analytics_report():
    """Verify general statistics analytics report formatting."""
    returns = pd.Series([0.01, -0.02, 0.03, -0.01] * 10)
    report = ReportGenerator.generate_analytics_report(returns)
    
    assert report["report_type"] == "Analytics Report"
    assert "sharpe_ratio" in report["metrics"]
    assert "ulcer_index" in report["metrics"]


def test_generate_backtest_report():
    """Verify Backtest Report summarizes trades and equity curves."""
    runner = StrategyRunner(initial_cash=5000.0)
    # Return empty ledger report
    report = ReportGenerator.generate_backtest_report(runner)
    
    assert report["report_type"] == "Backtest Report"
    assert report["summary"]["initial_cash"] == 5000.0
    assert report["summary"]["total_trades"] == 0


def test_generate_risk_report():
    """Verify Risk Report summarizes VaR and gross exposures."""
    returns = pd.Series([0.01, -0.02, 0.03, -0.01] * 10)
    equity = pd.Series([1000.0, 1010.0, 990.0, 1020.0])
    positions = {"AAPL": 400.0}
    
    report = ReportGenerator.generate_risk_report(
        returns=returns,
        equity_curve=equity,
        positions_value=positions,
        total_equity=1000.0,
    )
    
    assert report["report_type"] == "Risk Report"
    assert "var_historical" in report["risk_metrics"]
    assert report["risk_metrics"]["gross_exposure"] == 0.4


def test_generate_portfolio_report():
    """Verify Portfolio Report handles weights risk parity and correlation dictionary."""
    weights = {"AssetA": 0.5, "AssetB": 0.5}
    dates = pd.date_range(start="2026-01-01", periods=5)
    returns_df = pd.DataFrame({
        "AssetA": [0.01, -0.01, 0.02, 0.0, 0.015],
        "AssetB": [-0.005, 0.01, -0.01, 0.02, -0.005],
    }, index=dates)
    
    report = ReportGenerator.generate_portfolio_report(weights, returns_df)
    
    assert report["report_type"] == "Portfolio Report"
    assert "diversification_ratio" in report
    assert "risk_attribution" in report
    assert "AssetA" in report["correlation_matrix"]


def test_generate_optimization_report():
    """Verify Optimization Report summarizes parameter sweeps results."""
    sweeps = [
        {"parameters": {"ma": 50}, "metric_value": 2.0},
        {"parameters": {"ma": 30}, "metric_value": 1.1},
    ]
    report = ReportGenerator.generate_optimization_report(sweeps)
    
    assert report["report_type"] == "Optimization Report"
    assert report["sweeps_count"] == 2
    assert report["best_trial"]["parameters"]["ma"] == 50
