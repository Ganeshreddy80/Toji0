"""Statistical Hypothesis Testing (Hansen SPA, White Reality Check, and Stationary Bootstrap).
"""

from __future__ import annotations

import numpy as np
from typing import List


class StatisticalTestingSuite:
    """Implements multiple hypothesis testing adjustments and bootstrap validation methods."""

    @staticmethod
    def stationary_bootstrap(returns: np.ndarray, num_bootstrap: int = 100, p: float = 0.1) -> List[np.ndarray]:
        """Politis & Romano Stationary Bootstrap.

        Args:
            returns: Return series array of shape (T,).
            num_bootstrap: Number of bootstrap iterations to generate.
            p: Probability of starting a new block (geometric block length mean = 1/p).

        Returns:
            List of resampled bootstrap returns arrays.
        """
        N = len(returns)
        bootstraps = []

        for _ in range(num_bootstrap):
            boot_idx = np.zeros(N, dtype=int)
            # Pick a starting index randomly
            curr = np.random.randint(0, N)
            
            for i in range(N):
                boot_idx[i] = curr
                # With probability p, start a new block
                if np.random.rand() < p:
                    curr = np.random.randint(0, N)
                else:
                    curr = (curr + 1) % N
            bootstraps.append(returns[boot_idx])
            
        return bootstraps

    @classmethod
    def white_reality_check(
        cls,
        target_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        alternative_returns: List[np.ndarray],
        num_bootstrap: int = 100,
        p: float = 0.1
    ) -> float:
        """White's Reality Check for data-mining bias.

        Checks whether the best alternative strategy outperforms the benchmark.

        Returns:
            P-value of the test (high p-value implies performance is due to chance).
        """
        # Calculate excess returns relative to benchmark
        observed_excess = [np.mean(alt - benchmark_returns) for alt in alternative_returns]
        observed_target_excess = np.mean(target_returns - benchmark_returns)
        
        all_excess = observed_excess + [observed_target_excess]
        max_observed_excess = max(all_excess) if all_excess else 0.0

        # Construct bootstrap distributions
        # Vectorize/align length
        N = len(target_returns)
        centered_boot_maxes = []

        for _ in range(num_bootstrap):
            # Generate one bootstrap index array
            boot_idx = np.zeros(N, dtype=int)
            curr = np.random.randint(0, N)
            for i in range(N):
                boot_idx[i] = curr
                if np.random.rand() < p:
                    curr = np.random.randint(0, N)
                else:
                    curr = (curr + 1) % N

            # Evaluate each alternative on bootstrap sample
            boot_excesses = []
            for alt in alternative_returns:
                sample_alt = alt[boot_idx]
                sample_bench = benchmark_returns[boot_idx]
                
                # Excess return
                sample_excess = np.mean(sample_alt - sample_bench)
                # Centered excess (subtract the sample mean to enforce null hypothesis E[excess] = 0)
                mean_excess = np.mean(alt - benchmark_returns)
                boot_excesses.append(sample_excess - mean_excess)

            # Target centered excess
            sample_tar = target_returns[boot_idx]
            sample_bench = benchmark_returns[boot_idx]
            boot_excesses.append(np.mean(sample_tar - sample_bench) - observed_target_excess)

            centered_boot_maxes.append(max(boot_excesses))

        # P-value = proportion of bootstrap maxes >= observed max excess
        p_val = np.sum(np.array(centered_boot_maxes) >= max_observed_excess) / num_bootstrap
        return float(p_val)

    @classmethod
    def hansen_spa_test(
        cls,
        target_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        alternative_returns: List[np.ndarray],
        num_bootstrap: int = 100,
        p: float = 0.1
    ) -> float:
        """Hansen's Superior Predictive Ability (SPA) test.

        An improvement over White's Reality Check that uses a studentized/variance-scaled
        statistic and thresholding to ignore highly inferior models.

        Returns:
            SPA P-value.
        """
        # Similar bootstrap centering, but studentized by standard error
        # For simplicity and robust zero-dependency execution, we implement the studentized bootstrap p-value
        observed_excess = [np.mean(alt - benchmark_returns) for alt in alternative_returns]
        observed_target_excess = np.mean(target_returns - benchmark_returns)
        all_excess = observed_excess + [observed_target_excess]
        
        # Calculate standard errors
        std_errors = []
        for alt in alternative_returns + [target_returns]:
            excess = alt - benchmark_returns
            std_errors.append(np.std(excess) / np.sqrt(len(excess)) + 1e-10)

        studentized_excess = [mean / se for mean, se in zip(all_excess, std_errors)]
        max_observed_stat = max(studentized_excess) if studentized_excess else 0.0

        # Bootstrap
        N = len(target_returns)
        boot_max_stats = []

        for _ in range(num_bootstrap):
            # Bootstrap index
            boot_idx = np.zeros(N, dtype=int)
            curr = np.random.randint(0, N)
            for i in range(N):
                boot_idx[i] = curr
                if np.random.rand() < p:
                    curr = np.random.randint(0, N)
                else:
                    curr = (curr + 1) % N

            boot_stats = []
            for idx, alt in enumerate(alternative_returns + [target_returns]):
                sample_alt = alt[boot_idx]
                sample_bench = benchmark_returns[boot_idx]
                
                # Excess
                sample_excess = np.mean(sample_alt - sample_bench)
                # Centered excess
                mean_excess = all_excess[idx]
                centered = sample_excess - mean_excess
                
                # Studentize centered sample
                se = std_errors[idx]
                boot_stats.append(centered / se)

            boot_max_stats.append(max(boot_stats))

        p_val = np.sum(np.array(boot_max_stats) >= max_observed_stat) / num_bootstrap
        return float(p_val)
