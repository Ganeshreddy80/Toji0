"""Portfolio allocation and weight optimization engines."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd


class PortfolioAllocator:
    """Computes target portfolio allocation weights using quantitative models."""

    @staticmethod
    def equal_weights(symbols: list[str]) -> dict[str, float]:
        """Compute equal weight allocation weights."""
        n = len(symbols)
        if n == 0:
            return {}
        val = 1.0 / n
        return {sym: val for sym in symbols}

    @staticmethod
    def inverse_variance_weights(returns_df: pd.DataFrame) -> dict[str, float]:
        """Compute inverse variance weights where w_i is proportional to 1 / variance_i."""
        if returns_df.empty:
            return {}
            
        variances = returns_df.var(ddof=1)
        # Avoid division by zero
        variances = np.where(variances == 0.0, 1e-10, variances)
        
        inv_vars = 1.0 / variances
        sum_inv = np.sum(inv_vars)
        
        weights = inv_vars / sum_inv
        
        return {sym: float(w) for sym, w in zip(returns_df.columns, weights)}

    @staticmethod
    def risk_parity_weights(
        returns_df: pd.DataFrame,
        max_iter: int = 50,
        tolerance: float = 1e-6,
    ) -> dict[str, float]:
        """Compute Risk Parity (Equal Risk Contribution) weights using an iterative solver.
        
        Uses a self-contained multiplicative update algorithm to align risk contributions.
        Does not require external optimizers (scipy).
        """
        if returns_df.empty:
            return {}
            
        symbols = list(returns_df.columns)
        n = len(symbols)
        if n == 0:
            return {}
        if n == 1:
            return {symbols[0]: 1.0}
            
        # Covariance matrix
        Sigma = returns_df.cov().values
        
        # Initial guess: equal weights
        w = np.ones(n) / n
        
        # Target risk parity ratio for each asset is 1 / N
        target_rc_ratio = 1.0 / n
        
        for _ in range(max_iter):
            # Portfolio volatility
            port_variance = float(w.T @ Sigma @ w)
            port_vol = math.sqrt(max(port_variance, 1e-10))
            
            # Marginal Risk Contribution
            mrc = (Sigma @ w) / port_vol
            
            # Risk Contribution
            rc = w * mrc
            sum_rc = np.sum(rc)
            if sum_rc == 0.0:
                break
                
            rc_ratio = rc / sum_rc
            
            # Error tolerance check (Max absolute difference from target)
            error = np.max(np.abs(rc_ratio - target_rc_ratio))
            if error < tolerance:
                break
                
            # Multiplicative weight adjustment step
            w = w * (target_rc_ratio / (rc_ratio + 1e-10))
            # Re-normalize weights to sum to 1.0
            w_sum = np.sum(w)
            if w_sum == 0.0:
                w = np.ones(n) / n
            else:
                w = w / w_sum
                
        return {symbols[i]: float(w[i]) for i in range(n)}
