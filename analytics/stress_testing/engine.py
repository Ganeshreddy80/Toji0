"""Stress testing engine for evaluating strategy resilience under market shocks."""

from __future__ import annotations

from typing import Any, Callable
import numpy as np
import pandas as pd


class StressTester:
    """Applies synthetic volatility shocks, flash crashes, and transactional cost shocks to strategies."""

    @staticmethod
    def apply_flash_crash(
        returns: pd.Series,
        crash_index: int | None = None,
        crash_fraction: float = -0.20,
    ) -> pd.Series:
        """Inject a sudden, massive single-interval negative return shock into the returns series."""
        shocked = returns.copy()
        if len(shocked) == 0:
            return shocked
            
        idx = crash_index if crash_index is not None else len(shocked) // 2
        if 0 <= idx < len(shocked):
            # Locate target date label
            label = shocked.index[idx]
            shocked.loc[label] = crash_fraction
            
        return shocked

    @staticmethod
    def apply_volatility_shock(returns: pd.Series, variance_multiplier: float = 2.0) -> pd.Series:
        """Scale the returns variance to simulate high-volatility regimes."""
        if returns.empty:
            return returns
            
        mean = returns.mean()
        # Scale returns around their mean
        shocked = mean + (returns - mean) * np.sqrt(variance_multiplier)
        return shocked

    @staticmethod
    def simulate_cost_shocks(
        runner_factory: Callable[[float, float], Any],  # factory taking (slippage_multiplier, commission_multiplier)
        slippage_multiplier: float = 5.0,
        commission_multiplier: float = 3.0,
    ) -> Any:
        """Simulate strategy execution with inflated commission and slippage rates.
        
        Assumes the runner_factory builds and executes the StrategyRunner backtest simulation.
        
        Args:
            runner_factory: a callable returning the final completed StrategyRunner simulation
            slippage_multiplier: factor to scale slippage (simulates bid-ask spread expansion)
            commission_multiplier: factor to scale commission (simulates fee increases)
            
        Returns:
            StrategyRunner with stressed transaction costs.
        """
        return runner_factory(slippage_multiplier, commission_multiplier)
