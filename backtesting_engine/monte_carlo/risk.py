"""Risk Engine for Monte Carlo simulation risk metrics and ruin probabilities (Sprint 8C)."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from backtesting_engine.monte_carlo.models.monte_carlo import SimulationResult


class MonteCarloRiskEngine:
    """Computes tail risks, ruin probabilities, and loss distributions."""

    def compute_risk_metrics(self, simulations: List[SimulationResult]) -> Dict[str, Any]:
        """Compute complete risk metrics dictionary from simulation results.

        Args:
            simulations: List of SimulationResult objects.

        Returns:
            Dictionary containing probability of profit, loss, ruin, worst 5%, worst 1%,
            expected tail loss (CVaR 5%), and maximum observed drawdown.
        """
        if not simulations:
            return self._empty_risk_metrics()

        num_sims = len(simulations)

        total_returns = np.array([s.total_return for s in simulations], dtype=np.float64)
        max_drawdowns = np.array([s.max_drawdown for s in simulations], dtype=np.float64)
        ruin_flags = np.array([1 if s.ruin else 0 for s in simulations], dtype=np.int32)

        # Probabilities
        prob_profit = float(np.sum(total_returns > 0.0) / num_sims)
        prob_loss = float(np.sum(total_returns < 0.0) / num_sims)
        prob_ruin = float(np.sum(ruin_flags) / num_sims)

        # Tail percentiles
        worst_5_pct_return = float(np.percentile(total_returns, 5.0))
        worst_1_pct_return = float(np.percentile(total_returns, 1.0))

        worst_5_pct_drawdown = float(np.percentile(max_drawdowns, 95.0))
        worst_1_pct_drawdown = float(np.percentile(max_drawdowns, 99.0))

        # Expected Tail Loss (CVaR 5%): Average return in the worst 5% tail
        sorted_returns = np.sort(total_returns)
        cutoff_idx = max(1, int(np.floor(0.05 * num_sims)))
        tail_returns = sorted_returns[:cutoff_idx]
        expected_tail_return = float(np.mean(tail_returns))
        expected_tail_loss = -expected_tail_return if expected_tail_return < 0 else 0.0

        max_observed_drawdown = float(np.max(max_drawdowns))

        return {
            "probability_of_profit": prob_profit,
            "probability_of_loss": prob_loss,
            "probability_of_ruin": prob_ruin,
            "worst_5_pct_return": worst_5_pct_return,
            "worst_1_pct_return": worst_1_pct_return,
            "worst_5_pct_drawdown": worst_5_pct_drawdown,
            "worst_1_pct_drawdown": worst_1_pct_drawdown,
            "expected_tail_loss_5pct": expected_tail_loss,
            "expected_tail_return_5pct": expected_tail_return,
            "maximum_observed_drawdown": max_observed_drawdown,
        }

    def _empty_risk_metrics(self) -> Dict[str, Any]:
        """Return zeroed risk metrics when no simulations exist."""
        return {
            "probability_of_profit": 0.0,
            "probability_of_loss": 0.0,
            "probability_of_ruin": 0.0,
            "worst_5_pct_return": 0.0,
            "worst_1_pct_return": 0.0,
            "worst_5_pct_drawdown": 0.0,
            "worst_1_pct_drawdown": 0.0,
            "expected_tail_loss_5pct": 0.0,
            "expected_tail_return_5pct": 0.0,
            "maximum_observed_drawdown": 0.0,
        }
