"""Portfolio performance and risk contribution attribution engines."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd


class PerformanceAttributor:
    """Attributes returns, risk contributions, and diversification metrics to portfolio assets."""

    @staticmethod
    def calculate_risk_contribution(
        weights: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> dict[str, dict[str, float]]:
        """Compute the absolute and percentage risk contribution of each asset.
        
        Returns:
            dict of asset -> {
                "weight": float,
                "marginal_contribution": float,
                "absolute_contribution": float,
                "percentage_contribution": float
            }
        """
        if returns_df.empty or not weights:
            return {}
            
        symbols = list(returns_df.columns)
        n = len(symbols)
        
        # Sort weights vector to align with DataFrame columns
        w = np.array([weights.get(sym, 0.0) for sym in symbols])
        # Ensure weight sum is non-zero
        w_sum = np.sum(w)
        if w_sum > 0.0:
            w = w / w_sum
            
        Sigma = returns_df.cov().values
        
        port_variance = float(w.T @ Sigma @ w)
        port_vol = math.sqrt(max(port_variance, 1e-10))
        
        # Marginal Risk Contribution (MRC)
        mrc = (Sigma @ w) / port_vol
        
        # Absolute Risk Contribution (ARC)
        arc = w * mrc
        sum_arc = np.sum(arc)
        if sum_arc == 0.0:
            sum_arc = 1e-10
            
        percentage_contribution = arc / sum_arc
        
        attribution = {}
        for i, sym in enumerate(symbols):
            attribution[sym] = {
                "weight": float(w[i]),
                "marginal_contribution": float(mrc[i]),
                "absolute_contribution": float(arc[i]),
                "percentage_contribution": float(percentage_contribution[i]),
            }
            
        return attribution

    @staticmethod
    def diversification_ratio(
        weights: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> float:
        """Compute the Diversification Ratio of the portfolio.
        
        Formula: Sum(w_i * std_i) / portfolio_volatility
        A ratio > 1.0 indicates diversification benefits.
        """
        if returns_df.empty or not weights:
            return 1.0
            
        symbols = list(returns_df.columns)
        w = np.array([weights.get(sym, 0.0) for sym in symbols])
        w_sum = np.sum(w)
        if w_sum > 0.0:
            w = w / w_sum
            
        # Individual asset standard deviations
        stds = returns_df.std(ddof=1).values
        weighted_avg_vol = np.sum(w * stds)
        
        # Portfolio volatility
        Sigma = returns_df.cov().values
        port_variance = float(w.T @ Sigma @ w)
        port_vol = math.sqrt(max(port_variance, 1e-10))
        
        return float(weighted_avg_vol / port_vol)

    @staticmethod
    def return_attribution(
        weights: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> dict[str, float]:
        """Compute the weighted return contribution of each asset.
        
        Formula: Contribution_i = w_i * r_i
        """
        if returns_df.empty or not weights:
            return {}
            
        mean_returns = returns_df.mean()
        contributions = {}
        
        for sym in returns_df.columns:
            w = weights.get(sym, 0.0)
            r = mean_returns.get(sym, 0.0)
            contributions[sym] = float(w * r)
            
        return contributions
