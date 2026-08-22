"""Optimizer implementing Mean-Variance, Black-Litterman, and Hierarchical Risk Parity.
"""

from __future__ import annotations

import numpy as np
from datetime import datetime, timezone
from typing import List

from research_platform.portfolio_engine.interfaces import IPortfolioOptimizer
from research_platform.portfolio_engine.models import (
    CovarianceMatrix,
    ForecastResult,
    OptimizationResult,
    PortfolioWeights
)


class PortfolioOptimizer(IPortfolioOptimizer):
    """Executes Mean-Variance, Black-Litterman, and Hierarchical Risk Parity optimizations."""

    def __init__(self, optimizer_name: str = "max_sharpe") -> None:
        self.optimizer_name = optimizer_name

    def optimize(
        self,
        symbols: List[str],
        forecast: ForecastResult,
        covariance: CovarianceMatrix
    ) -> OptimizationResult:
        """Calculate optimized weight allocations under objective choices."""
        n = len(symbols)
        if n == 0:
            return OptimizationResult(
                optimizer_name=self.optimizer_name.upper(),
                weights=PortfolioWeights(weights={}, timestamp=datetime.now(timezone.utc)),
                expected_return=0.0,
                expected_volatility=0.0,
                sharpe_ratio=0.0
            )

        cov_mat = np.array(covariance.matrix)
        # Expected returns vector
        mu = np.array([forecast.forecasts.get(sym, 0.0) for sym in symbols])

        # Regularize covariance to guarantee invertibility (add small epsilon along diagonal)
        cov_mat += np.eye(n) * 1e-6
        inv_cov = np.linalg.inv(cov_mat)

        if self.optimizer_name == "min_variance":
            # w = inv_cov @ ones / (ones.T @ inv_cov @ ones)
            ones = np.ones(n)
            raw_w = inv_cov @ ones
            w = raw_w / (ones.T @ raw_w + 1e-10)
        elif self.optimizer_name == "black_litterman":
            # Simple BL implementation using market equilibriums
            # Adjusted returns mu_BL
            mu_bl = self._apply_black_litterman(mu, cov_mat)
            raw_w = inv_cov @ mu_bl
            # Clip weights to positive values (long-only proxy) and normalize
            clipped_w = np.clip(raw_w, 0.0, None)
            w = clipped_w / (np.sum(clipped_w) + 1e-10)
        elif self.optimizer_name == "hrp":
            # Hierarchical Risk Parity (HRP)
            w = self._hierarchical_risk_parity(cov_mat)
        else:
            # Maximum Sharpe tangency portfolio (w = inv_cov @ mu / (ones.T @ inv_cov @ mu))
            raw_w = inv_cov @ mu
            clipped_w = np.clip(raw_w, 0.0, None)
            w = clipped_w / (np.sum(clipped_w) + 1e-10)

        weights_dict = {symbols[i]: float(w[i]) for i in range(n)}
        
        # Calculate portfolios metrics
        expected_ret = float(np.dot(w, mu))
        expected_vol = float(np.sqrt(w.T @ cov_mat @ w))
        sharpe = expected_ret / (expected_vol + 1e-10)

        return OptimizationResult(
            optimizer_name=self.optimizer_name.upper(),
            weights=PortfolioWeights(weights=weights_dict, timestamp=datetime.now(timezone.utc)),
            expected_return=expected_ret,
            expected_volatility=expected_vol,
            sharpe_ratio=sharpe
        )

    def _apply_black_litterman(
        self,
        mu: np.ndarray,
        cov: np.ndarray,
        tau: float = 0.05
    ) -> np.ndarray:
        """Apply simple view adjustment based on market equilibrium returns (Black-Litterman)."""
        # Assume a simple diagonal view matrix targeting high momentum assets
        n = mu.shape[0]
        P = np.eye(n)
        Q = mu + np.random.normal(0, 0.001, n)  # views shifted slightly
        Omega = np.diag(np.diag(cov)) * tau

        # BL Formula:
        # mu_bl = inv( inv(tau*S) + P.T @ inv(Omega) @ P ) @ ( inv(tau*S) @ Pi + P.T @ inv(Omega) @ Q )
        inv_tau_cov = np.linalg.inv(cov * tau)
        inv_omega = np.linalg.inv(Omega)

        part1 = np.linalg.inv(inv_tau_cov + P.T @ inv_omega @ P)
        part2 = inv_tau_cov @ mu + P.T @ inv_omega @ Q
        
        return part1 @ part2

    def _hierarchical_risk_parity(self, cov: np.ndarray) -> np.ndarray:
        """Hierarchical Risk Parity (HRP) recursive bisection weight calculation.

        Clusters weights without covariance inversion.
        """
        n = cov.shape[0]
        # Basic correlation matrix
        d = np.diag(cov)
        std = np.sqrt(d)
        corr = cov / np.outer(std, std)

        # Simple hierarchical division based on correlation clustering distance
        # We recursively bisect the array index and calculate inverse variance allocation
        weights = np.ones(n) / n
        
        # Compute inverse-variance weights for all assets
        inv_var = 1.0 / (d + 1e-10)
        
        # Run recursive bisection proxy
        def bisect(items: List[int]) -> np.ndarray:
            if len(items) <= 1:
                return np.ones(len(items))

            mid = len(items) // 2
            left = items[:mid]
            right = items[mid:]

            # Compute cluster variances
            inv_var_l = inv_var[left]
            inv_var_r = inv_var[right]
            
            w_l = inv_var_l / np.sum(inv_var_l)
            w_r = inv_var_r / np.sum(inv_var_r)

            var_l = w_l.T @ cov[np.ix_(left, left)] @ w_l
            var_r = w_r.T @ cov[np.ix_(right, right)] @ w_r

            alpha = 1.0 - (var_l / (var_l + var_r + 1e-10))
            
            w_left = bisect(left) * alpha
            w_right = bisect(right) * (1.0 - alpha)
            return np.concatenate([w_left, w_right])

        items = list(range(n))
        weights = bisect(items)
        return weights / np.sum(weights)
