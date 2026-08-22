"""Walk Forward Optimization split generator and Monte Carlo simulator."""

from __future__ import annotations

import logging
import random
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """Generates train/validation windows splits for robust strategy backtests."""

    def generate_splits(
        self,
        data_length: int,
        train_size: int,
        validation_size: int,
        step_size: int
    ) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Creates sliding walk-forward indices tuples: ((train_start, train_end), (val_start, val_end))."""
        splits = []
        start = 0

        while start + train_size + validation_size <= data_length:
            train_end = start + train_size
            val_end = train_end + validation_size
            
            splits.append(((start, train_end), (train_end, val_end)))
            start += step_size

        return splits


class MonteCarloSimulator:
    """Simulates multiple random equity curves to evaluate risk parameters."""

    def run_simulations(
        self,
        historical_returns: List[float],
        n_simulations: int = 1000,
        horizon_days: int = 30,
        initial_capital: float = 100000.0
    ) -> Dict[str, Any]:
        if not historical_returns:
            return {"ruin_probability": 0.0, "median_ending_value": initial_capital}

        runs = []
        ruin_count = 0
        ruin_threshold = initial_capital * 0.70  # Ruin if capital drops by 30%

        for _ in range(n_simulations):
            equity = initial_capital
            peak = initial_capital
            max_dd = 0.0
            
            # Sample returns with replacement
            sim_returns = random.choices(historical_returns, k=horizon_days)
            for r in sim_returns:
                equity *= (1.0 + r)
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
                if equity < ruin_threshold:
                    ruin_count += 1
                    break
            runs.append(equity)

        ruin_prob = ruin_count / n_simulations
        runs.sort()
        median_val = runs[n_simulations // 2]

        return {
            "ruin_probability": float(ruin_prob),
            "median_ending_value": float(median_val),
            "min_ending_value": float(runs[0]),
            "max_ending_value": float(runs[-1])
        }
