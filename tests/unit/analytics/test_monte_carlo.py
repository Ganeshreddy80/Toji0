"""Unit tests for the MonteCarloSimulator returns bootstrapping and trade sequence randomisation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.monte_carlo.simulator import MonteCarloSimulator


def test_bootstrap_returns():
    """Verify bootstrap resamples returns series with replacement."""
    returns = pd.Series([0.01, -0.02, 0.03, -0.01])
    sims = MonteCarloSimulator.bootstrap_returns(returns, n_simulations=10, length=20)
    
    assert sims.shape == (10, 20)
    # Check that all elements in sims are present in the original returns
    for row in sims:
        for val in row:
            assert val in returns.values


def test_randomize_trade_sequence():
    """Verify trade sequence randomisation shuffles trades without replacement."""
    trades = pd.Series([100.0, -50.0, 200.0])
    sims = MonteCarloSimulator.randomize_trade_sequence(trades, n_simulations=5)
    
    assert sims.shape == (5, 3)
    # Verify that the sorted values in each shuffled sequence equal the sorted original trades
    sorted_orig = sorted(trades.values)
    for row in sims:
        assert sorted(row) == sorted_orig


def test_simulate_equity_paths():
    """Verify equity path accumulation for compounded returns and cash PnL."""
    sim_returns = np.array([
        [0.01, 0.01],
        [-0.01, -0.01]
    ])
    
    # Compounded returns
    paths_comp = MonteCarloSimulator.simulate_equity_paths(
        initial_equity=100.0,
        simulated_returns=sim_returns,
        is_pnl_cash=False
    )
    assert paths_comp.shape == (2, 3)
    assert pytest.approx(paths_comp[0, 2]) == 100.0 * 1.01 * 1.01
    assert pytest.approx(paths_comp[1, 2]) == 100.0 * 0.99 * 0.99
    
    # Cash PnL
    sim_pnl = np.array([
        [10.0, 20.0],
        [-10.0, -20.0]
    ])
    paths_cash = MonteCarloSimulator.simulate_equity_paths(
        initial_equity=100.0,
        simulated_returns=sim_pnl,
        is_pnl_cash=True
    )
    assert paths_cash[0, 2] == 130.0
    assert paths_cash[1, 2] == 70.0


def test_calculate_ruin_probability():
    """Verify that ruin probability counts paths correctly."""
    paths = np.array([
        [100.0, 80.0, 40.0],  # ruined (< 50)
        [100.0, 90.0, 85.0],  # not ruined
        [100.0, 45.0, 60.0],  # ruined (< 50)
    ])
    
    ruin_prob = MonteCarloSimulator.calculate_ruin_probability(paths, ruin_threshold=50.0)
    assert ruin_prob == 2.0 / 3.0


def test_analyze_worst_case_and_intervals():
    """Verify worst-case and quantile reports."""
    paths = np.array([
        [100.0, 80.0, 90.0],
        [100.0, 70.0, 60.0],
        [100.0, 110.0, 120.0]
    ])
    
    worst_metrics = MonteCarloSimulator.analyze_worst_case(paths)
    assert worst_metrics["worst_ending_equity"] == 60.0
    
    # Max drawdowns:
    # Path 1: 100 -> 80 (-20%), peak is 100. Max dd is -20%
    # Path 2: 100 -> 70 -> 60 (-40%), max dd is -40%
    # Path 3: no drawdown (max dd 0%)
    # Worst drawdown across all is -40%
    assert pytest.approx(worst_metrics["worst_drawdown"]) == -0.40
    
    quantiles = MonteCarloSimulator.calculate_confidence_intervals(paths, quantiles=[0.0, 1.0])
    assert quantiles[0.0] == 60.0
    assert quantiles[1.0] == 120.0
stream_result = None
