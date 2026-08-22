"""Unit tests for the portfolio allocation and performance/risk attribution engines."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.portfolio.allocator import PortfolioAllocator
from analytics.portfolio.attribution import PerformanceAttributor


@pytest.fixture
def returns_df() -> pd.DataFrame:
    """Fixture providing simulated daily returns for 3 assets."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=100)
    data = {
        "AssetA": np.random.normal(0.0005, 0.01, 100),
        "AssetB": np.random.normal(0.0008, 0.02, 100),
        "AssetC": np.random.normal(0.0002, 0.015, 100),
    }
    return pd.DataFrame(data, index=dates)


def test_equal_weights():
    """Verify equal weights splits."""
    w = PortfolioAllocator.equal_weights(["A", "B", "C"])
    assert len(w) == 3
    assert w["A"] == 1.0 / 3.0


def test_inverse_variance_weights(returns_df: pd.DataFrame):
    """Verify inverse variance weights scaling."""
    w = PortfolioAllocator.inverse_variance_weights(returns_df)
    assert len(w) == 3
    # Sum of weights should equal 1.0
    assert pytest.approx(sum(w.values())) == 1.0
    # AssetB is most volatile (std 0.02), so it should get the lowest weight
    assert w["AssetB"] < w["AssetA"]
    assert w["AssetB"] < w["AssetC"]


def test_risk_parity_weights(returns_df: pd.DataFrame):
    """Verify Risk Parity iterative solver convergence."""
    w = PortfolioAllocator.risk_parity_weights(returns_df, max_iter=100)
    assert len(w) == 3
    assert pytest.approx(sum(w.values())) == 1.0
    
    # Calculate risk contributions to verify they are equalized
    attrib = PerformanceAttributor.calculate_risk_contribution(w, returns_df)
    rc_a = attrib["AssetA"]["percentage_contribution"]
    rc_b = attrib["AssetB"]["percentage_contribution"]
    rc_c = attrib["AssetC"]["percentage_contribution"]
    
    # Each should have approximately 1/3 (0.333333) risk contribution
    assert pytest.approx(rc_a, abs=1e-2) == 1.0 / 3.0
    assert pytest.approx(rc_b, abs=1e-2) == 1.0 / 3.0
    assert pytest.approx(rc_c, abs=1e-2) == 1.0 / 3.0


def test_performance_attribution(returns_df: pd.DataFrame):
    """Verify diversification ratio and return contribution logic."""
    weights = {"AssetA": 0.4, "AssetB": 0.3, "AssetC": 0.3}
    
    div = PerformanceAttributor.diversification_ratio(weights, returns_df)
    assert isinstance(div, float)
    assert div >= 1.0  # Asset correlation is near zero, so diversification ratio should be > 1.0
    
    ret_contrib = PerformanceAttributor.return_attribution(weights, returns_df)
    assert len(ret_contrib) == 3
    assert ret_contrib["AssetA"] == pytest.approx(0.4 * returns_df["AssetA"].mean())
