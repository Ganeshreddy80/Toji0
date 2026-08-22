"""Calculates portfolio metrics: Sharpe, Sortino, Calmar, Alpha, and Beta."""

from __future__ import annotations

import logging
from typing import List
import math
from research_platform.portfolio_intelligence.models import PortfolioPerformanceMetrics

logger = logging.getLogger(__name__)


class PortfolioMetricsCalculator:
    """Computes investment risk/return ratios from a series of periodic returns."""

    def calculate_ratios(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float],
        risk_free_rate: float = 0.02
    ) -> PortfolioPerformanceMetrics:
        n_periods = len(portfolio_returns)
        if n_periods < 3:
            return PortfolioPerformanceMetrics(
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                alpha=0.0,
                beta=1.0
            )

        # Standardize periods to annual base
        annual_factor = 252.0  # Daily returns assumption
        
        # Calculate returns stats
        mean_ret = sum(portfolio_returns) / n_periods
        annual_ret = mean_ret * annual_factor
        
        # Variance / standard deviation
        var = sum((x - mean_ret) ** 2 for x in portfolio_returns) / (n_periods - 1)
        std = math.sqrt(var)
        annual_std = std * math.sqrt(annual_factor)

        # 1. Sharpe Ratio
        if annual_std > 0.0:
            sharpe = (annual_ret - risk_free_rate) / annual_std
        else:
            sharpe = 0.0

        # 2. Sortino Ratio (Downside deviation only)
        downside_returns = [x for x in portfolio_returns if x < 0.0]
        if downside_returns:
            downside_var = sum(x ** 2 for x in downside_returns) / n_periods
            downside_std = math.sqrt(downside_var) * math.sqrt(annual_factor)
        else:
            downside_std = 0.0

        if downside_std > 0.0:
            sortino = (annual_ret - risk_free_rate) / downside_std
        else:
            sortino = 0.0

        # 3. Calmar Ratio (Maximum Drawdown based)
        # Compute drawdown series
        cum_ret = 1.0
        peak = 1.0
        max_dd = 0.001
        for r in portfolio_returns:
            cum_ret *= (1.0 + r)
            if cum_ret > peak:
                peak = cum_ret
            dd = (peak - cum_ret) / peak
            if dd > max_dd:
                max_dd = dd

        calmar = annual_ret / max_dd

        # 4. Beta and Alpha
        # Ensure benchmark is aligned in length
        min_len = min(n_periods, len(benchmark_returns))
        p_slice = portfolio_returns[-min_len:]
        b_slice = benchmark_returns[-min_len:]
        
        mean_b = sum(b_slice) / min_len
        var_b = sum((x - mean_b) ** 2 for x in b_slice) / (min_len - 1)
        cov = sum((x - sum(p_slice)/min_len) * (y - mean_b) for x, y in zip(p_slice, b_slice)) / (min_len - 1)

        if var_b > 0.0:
            beta = cov / var_b
        else:
            beta = 1.0

        # Alpha = PortfolioReturn - [RiskFree + Beta * (BenchmarkReturn - RiskFree)]
        annual_bench = mean_b * annual_factor
        alpha = annual_ret - (risk_free_rate + beta * (annual_bench - risk_free_rate))

        return PortfolioPerformanceMetrics(
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            calmar_ratio=float(calmar),
            alpha=float(alpha),
            beta=float(beta)
        )
