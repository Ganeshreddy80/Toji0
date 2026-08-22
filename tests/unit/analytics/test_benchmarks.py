"""Unit tests for the BenchmarkEngine benchmarking and comparison metrics."""

from __future__ import annotations

import pandas as pd
import pytest

from analytics.benchmarks.engine import BenchmarkEngine


@pytest.fixture
def price_data() -> pd.Series:
    """Fixture returning a simple pricing series."""
    dates = pd.date_range(start="2026-01-01", periods=5)
    return pd.Series([100.0, 102.0, 101.0, 105.0, 110.0], index=dates)


@pytest.fixture
def multi_price_data() -> pd.DataFrame:
    """Fixture returning a DataFrame of pricing series for multiple assets."""
    dates = pd.date_range(start="2026-01-01", periods=5)
    return pd.DataFrame({
        "AssetA": [100.0, 102.0, 101.0, 105.0, 110.0],
        "AssetB": [50.0, 49.0, 52.0, 51.0, 55.0],
    }, index=dates)


def test_buy_and_hold(price_data: pd.Series):
    """Verify Buy & Hold curve matches exact price ratios."""
    curve = BenchmarkEngine.buy_and_hold(price_data, initial_cash=1000.0)
    assert len(curve) == 5
    assert curve.iloc[0] == 1000.0
    # At index 4, price is 110. Ratio 1.1. Equity = 1100.0.
    assert curve.iloc[4] == 1100.0


def test_equal_weight(multi_price_data: pd.DataFrame):
    """Verify Equal Weight portfolio compounds daily returns average."""
    curve = BenchmarkEngine.equal_weight(multi_price_data, initial_cash=1000.0)
    assert len(curve) == 5
    assert curve.iloc[0] == 1000.0
    # Day 1: AssetA return = 0.02, AssetB return = -0.02. Avg = 0.0.
    assert curve.iloc[1] == 1000.0


def test_random_entry(price_data: pd.Series):
    """Verify Random Entry returns a Series index aligned with price index."""
    curve = BenchmarkEngine.random_entry(price_data, initial_cash=1000.0, num_runs=5)
    assert len(curve) == 5
    assert curve.index.equals(price_data.index)


def test_compare_performance():
    """Verify tracking error and information ratio calculations."""
    dates = pd.date_range(start="2026-01-01", periods=5)
    strat_eq = pd.Series([100.0, 102.0, 105.0, 103.0, 108.0], index=dates)
    bench_eq = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=dates)
    
    report = BenchmarkEngine.compare_performance(strat_eq, bench_eq, periods_per_year=252)
    assert "strategy_return" in report
    assert "benchmark_return" in report
    assert "active_premium" in report
    assert "tracking_error" in report
    assert "information_ratio" in report
