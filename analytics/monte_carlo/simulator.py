"""Monte Carlo simulations for strategy returns bootstrapping and trade sequence randomisation."""

from __future__ import annotations

import numpy as np
import pandas as pd


class MonteCarloSimulator:
    """Orchestrates bootstrap and trade randomisation runs to calculate confidence metrics."""

    @staticmethod
    def bootstrap_returns(
        returns: pd.Series | np.ndarray,
        n_simulations: int = 1000,
        length: int | None = None,
    ) -> np.ndarray:
        """Construct synthetic returns paths using bootstrap sampling with replacement.
        
        Returns a 2D numpy array of shape (n_simulations, length).
        """
        ret_arr = np.asarray(returns)
        n = len(ret_arr)
        if n == 0:
            return np.zeros((n_simulations, 0))
            
        sim_len = length if length is not None else n
        
        # Vectorized choice of indices
        indices = np.random.choice(n, size=(n_simulations, sim_len), replace=True)
        return ret_arr[indices]

    @staticmethod
    def randomize_trade_sequence(
        trades_pnl: pd.Series | np.ndarray,
        n_simulations: int = 1000,
    ) -> np.ndarray:
        """Construct synthetic trade ledger sequences by shuffling trade returns without replacement.
        
        Returns a 2D numpy array of shape (n_simulations, len(trades_pnl)).
        """
        pnl_arr = np.asarray(trades_pnl)
        n = len(pnl_arr)
        if n == 0:
            return np.zeros((n_simulations, 0))
            
        shuffled = np.zeros((n_simulations, n))
        for i in range(n_simulations):
            perm = np.random.permutation(pnl_arr)
            shuffled[i] = perm
            
        return shuffled

    @staticmethod
    def simulate_equity_paths(
        initial_equity: float,
        simulated_returns: np.ndarray,  # shape (n_simulations, steps)
        is_pnl_cash: bool = False,
    ) -> np.ndarray:
        """Generate cumulative equity curves from simulated returns or cash PnL values.
        
        Returns a 2D numpy array of shape (n_simulations, steps + 1).
        """
        n_sims, steps = simulated_returns.shape
        paths = np.zeros((n_sims, steps + 1))
        paths[:, 0] = initial_equity
        
        if is_pnl_cash:
            # Add cash flows directly
            paths[:, 1:] = initial_equity + np.cumsum(simulated_returns, axis=1)
        else:
            # Compound returns
            paths[:, 1:] = initial_equity * np.cumprod(simulated_returns + 1.0, axis=1)
            
        return paths

    @staticmethod
    def calculate_ruin_probability(
        equity_paths: np.ndarray,
        ruin_threshold: float,
    ) -> float:
        """Compute the fraction of simulated paths where equity drops below the ruin threshold."""
        n_sims = equity_paths.shape[0]
        if n_sims == 0:
            return 1.0
            
        # Any path that hits or falls below the threshold at any point
        ruined = np.any(equity_paths <= ruin_threshold, axis=1)
        return float(np.sum(ruined) / n_sims)

    @staticmethod
    def analyze_worst_case(equity_paths: np.ndarray) -> dict[str, float]:
        """Identify the absolute worst ending equity and worst peak-to-trough drawdown."""
        n_sims = equity_paths.shape[0]
        if n_sims == 0:
            return {"worst_ending_equity": 0.0, "worst_drawdown": -1.0}
            
        ending_equity = equity_paths[:, -1]
        worst_ending = np.min(ending_equity)
        
        # Calculate max drawdowns for each path
        drawdowns = []
        for i in range(n_sims):
            path = equity_paths[i]
            running_max = np.maximum.accumulate(path)
            running_max = np.where(running_max == 0.0, 1e-10, running_max)
            dd = (path - running_max) / running_max
            drawdowns.append(np.min(dd))
            
        return {
            "worst_ending_equity": float(worst_ending),
            "worst_drawdown": float(np.min(drawdowns)),
        }

    @staticmethod
    def calculate_confidence_intervals(
        equity_paths: np.ndarray,
        quantiles: list[float] | None = None,
    ) -> dict[float, float]:
        """Compute final equity quantile levels (confidence intervals)."""
        if quantiles is None:
            quantiles = [0.05, 0.25, 0.50, 0.75, 0.95]
            
        ending_equity = equity_paths[:, -1]
        results = {}
        for q in quantiles:
            results[q] = float(np.percentile(ending_equity, q * 100))
            
        return results
