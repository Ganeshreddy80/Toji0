"""Robust Statistics module (Newey-West HAC standard errors, robust t-statistics).
"""

from __future__ import annotations

import math
import numpy as np


class RobustStatistics:
    """Calculates Heteroskedasticity and Autocorrelation Consistent (HAC) statistical estimates."""

    @staticmethod
    def newey_west_t_stat(returns: np.ndarray, lag: int = None) -> tuple[float, float]:
        """Compute the Newey-West HAC adjusted standard error and robust t-statistic.

        Args:
            returns: Return series array of shape (T,).
            lag: Lag bandwidth. If None, uses $4 * (T / 100) ** (2/9)$.

        Returns:
            Tuple of (robust_t_statistic, robust_standard_error).
        """
        T = len(returns)
        if T < 4:
            return 0.0, 1.0

        mean = float(np.mean(returns))
        # Residuals
        e = returns - mean

        # Set default lag bandwidth
        if lag is None:
            lag = int(math.ceil(4.0 * (T / 100.0) ** (2.0 / 9.0)))
        lag = min(lag, T - 2)

        # 1. Variance term (heteroskedasticity)
        V = np.sum(e ** 2) / T

        # 2. Covariance terms (autocorrelation) with Bartlett weights
        for j in range(1, lag + 1):
            weight = 1.0 - (j / (lag + 1.0))
            cov = np.sum(e[j:] * e[:-j]) / T
            V += 2.0 * weight * cov

        # Ensure non-negative variance
        V = max(V, 1e-10)
        
        # Robust Standard Error
        robust_se = math.sqrt(V / T)
        robust_t = mean / (robust_se + 1e-10)

        return robust_t, robust_se
