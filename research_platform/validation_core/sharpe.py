"""Sharpe Ratio, Probabilistic Sharpe Ratio (PSR), and Deflated Sharpe Ratio (DSR).
"""

from __future__ import annotations

import math
from typing import List


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Percent point function (inverse CDF) for standard normal distribution."""
    if p <= 0.0:
        return -9.0
    if p >= 1.0:
        return 9.0
    
    # Simple, highly accurate binary search
    low, high = -9.0, 9.0
    for _ in range(50):
        mid = (low + high) / 2.0
        val = norm_cdf(mid)
        if val < p:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


class SharpeValidator:
    """Computes Sharpe ratios, PSR, and DSR using higher-order returns moments."""

    @staticmethod
    def calculate_moments(returns: List[float]) -> tuple[float, float, float, float]:
        """Compute mean, std deviation, skewness, and kurtosis of returns series.

        Returns:
            Tuple of (mean, std, skewness, kurtosis).
        """
        N = len(returns)
        if N < 4:
            return 0.0, 1.0, 0.0, 3.0

        mean = float(sum(returns) / N)
        variance = float(sum((x - mean) ** 2 for x in returns) / (N - 1))
        std = math.sqrt(variance)

        if std == 0:
            return mean, 0.0, 0.0, 3.0

        # Calculate Skewness and Kurtosis
        skew = sum((x - mean) ** 3 for x in returns) / (N * (std ** 3))
        kurt = sum((x - mean) ** 4 for x in returns) / (N * (std ** 4))

        return mean, std, float(skew), float(kurt)

    @classmethod
    def calculate_psr(
        cls,
        returns: List[float],
        benchmark_sr: float = 0.0,
        annualization_factor: float = 252.0
    ) -> float:
        """Compute the Probabilistic Sharpe Ratio (PSR)."""
        N = len(returns)
        if N < 4:
            return 0.5

        mean, std, skew, kurt = cls.calculate_moments(returns)
        if std == 0:
            return 0.5

        # Daily Sharpe Ratio
        sr = mean / std
        
        # Annualized Sharpe Ratio
        sr_annual = sr * math.sqrt(annualization_factor)
        sr_benchmark_daily = benchmark_sr / math.sqrt(annualization_factor)

        # Standard deviation of Sharpe ratio estimate:
        # std_sr = sqrt( (1 - skew * sr + (kurt - 1) / 4 * sr^2) / (N - 1) )
        numerator = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * (sr ** 2)
        std_sr = math.sqrt(max(numerator, 1e-10) / (N - 1.0))

        t_stat = (sr - sr_benchmark_daily) / std_sr
        return norm_cdf(t_stat)

    @classmethod
    def calculate_dsr(
        cls,
        returns: List[float],
        all_trials_srs: List[float],
        annualization_factor: float = 252.0
    ) -> float:
        """Compute the Deflated Sharpe Ratio (DSR)."""
        M = len(all_trials_srs)
        if M <= 1:
            return cls.calculate_psr(returns, benchmark_sr=0.0, annualization_factor=annualization_factor)

        # Variance of Sharpe ratios across all trials
        mean_trial_sr = sum(all_trials_srs) / M
        var_trial_sr = sum((x - mean_trial_sr) ** 2 for x in all_trials_srs) / (M - 1)
        std_trial_sr = math.sqrt(max(var_trial_sr, 1e-10))

        # Euler-Mascheroni constant
        gamma = 0.5772156649

        # Deflated Sharpe Ratio benchmark:
        # SR_0* = std_trial_sr * ( (1-gamma) * Z^-1(1 - 1/M) + gamma * Z^-1(1 - 1/(M * e)) )
        val1 = 1.0 - (1.0 / M)
        val2 = 1.0 - (1.0 / (M * math.e))

        z1 = norm_ppf(max(val1, 0.5))
        z2 = norm_ppf(max(val2, 0.5))

        benchmark_sr = std_trial_sr * ((1.0 - gamma) * z1 + gamma * z2)
        
        # Returns PSR using calculated benchmark
        return cls.calculate_psr(returns, benchmark_sr=benchmark_sr, annualization_factor=annualization_factor)
