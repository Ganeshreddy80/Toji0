"""Unit tests for the StressTester strategy resilience and market shock evaluator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.stress_testing.engine import StressTester


def test_apply_flash_crash():
    """Verify flash crash injection at specific indices."""
    dates = pd.date_range(start="2026-01-01", periods=10)
    returns = pd.Series([0.001] * 10, index=dates)
    
    # Apply -20% crash at index 5
    shocked = StressTester.apply_flash_crash(returns, crash_index=5, crash_fraction=-0.20)
    assert shocked.iloc[5] == -0.20
    assert shocked.iloc[0] == 0.001
    assert shocked.iloc[9] == 0.001


def test_apply_volatility_shock():
    """Verify returns variance scaling."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=100)
    returns = pd.Series(np.random.normal(0.0005, 0.01, 100), index=dates)
    
    orig_std = returns.std(ddof=1)
    
    # Scale variance by 4x -> standard deviation should scale by 2x (sqrt(4))
    shocked = StressTester.apply_volatility_shock(returns, variance_multiplier=4.0)
    shocked_std = shocked.std(ddof=1)
    
    assert pytest.approx(shocked_std) == orig_std * 2.0


def test_simulate_cost_shocks():
    """Verify cost shocks simulate transaction fee and slippage inflation."""
    # Dummy strategy runner factory
    def mock_factory(slip_mult: float, comm_mult: float) -> tuple[float, float]:
        return slip_mult, comm_mult
        
    s_mult, c_mult = StressTester.simulate_cost_shocks(
        runner_factory=mock_factory,
        slippage_multiplier=5.0,
        commission_multiplier=3.0,
    )
    
    assert s_mult == 5.0
    assert c_mult == 3.0
