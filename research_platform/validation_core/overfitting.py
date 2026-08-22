"""Probability of Backtest Overfitting (PBO) computation engine.
"""

from __future__ import annotations

import numpy as np
from typing import List


class OverfittingDetector:
    """Calculates Probability of Backtest Overfitting (PBO) from strategy trial returns."""

    @staticmethod
    def calculate_pbo(trials_returns: List[np.ndarray], num_splits: int = 10) -> float:
        """Compute the PBO score.

        Args:
            trials_returns: List of return series arrays (each array is steps length)
                            representing trials of strategy configurations.
            num_splits: Number of cross-validation splits to construct.

        Returns:
            Probability of Backtest Overfitting (0.0 to 1.0).
        """
        if not trials_returns or len(trials_returns) < 2:
            return 0.0

        n_trials = len(trials_returns)
        length = len(trials_returns[0])
        
        # Partition data into splits
        block_size = length // num_splits
        if block_size < 2:
            return 0.0

        overfit_count = 0
        total_runs = 0

        # Construct splits
        for i in range(num_splits):
            test_start = i * block_size
            test_end = (i + 1) * block_size
            
            # Divide each trial into IS (In-Sample) and OOS (Out-of-Sample)
            is_sharpes = []
            oos_sharpes = []

            for trial in trials_returns:
                # OOS is the current split
                oos_ret = trial[test_start:test_end]
                # IS is the rest
                is_ret = np.concatenate([trial[:test_start], trial[test_end:]])

                # Calculate simplified Sharpe ratios
                is_sharpe = np.mean(is_ret) / (np.std(is_ret) + 1e-10)
                oos_sharpe = np.mean(oos_ret) / (np.std(oos_ret) + 1e-10)

                is_sharpes.append(is_sharpe)
                oos_sharpes.append(oos_sharpe)

            # Find IS optimal trial index
            best_is_idx = int(np.argmax(is_sharpes))

            # Find OOS rank of the best IS trial
            oos_ranks = np.argsort(np.argsort(oos_sharpes))
            best_oos_rank = oos_ranks[best_is_idx]
            
            # Check if rank is below median (which is (n_trials - 1) / 2)
            median_rank = (n_trials - 1) / 2.0
            if best_oos_rank < median_rank:
                overfit_count += 1
            total_runs += 1

        return float(overfit_count / total_runs) if total_runs > 0 else 0.0
