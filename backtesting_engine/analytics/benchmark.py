"""Benchmark Provider abstraction interface and default benchmark provider (Sprint 8A-H)."""

from __future__ import annotations

import abc
from typing import List, Optional

from backtesting_engine.analytics.models.analytics import AnalyticsContext, BenchmarkComparison


class IBenchmarkProvider(abc.ABC):
    """Abstract interface for fetching and computing benchmark comparison metrics (Open/Closed Principle)."""

    @abc.abstractmethod
    def calculate_benchmark_comparison(
        self,
        portfolio_returns: List[float],
        portfolio_total_return: float,
        context: AnalyticsContext,
    ) -> Optional[BenchmarkComparison]:
        """Compute benchmark beta, alpha, correlation, and outperformance relative to portfolio returns."""


class DefaultBenchmarkProvider(IBenchmarkProvider):
    """Default benchmark provider architecture supporting optional benchmark returns series."""

    def calculate_benchmark_comparison(
        self,
        portfolio_returns: List[float],
        portfolio_total_return: float,
        context: AnalyticsContext,
    ) -> Optional[BenchmarkComparison]:
        """Compute benchmark statistics if benchmark_name and benchmark_returns are configured in context."""
        if not context.benchmark_name or not context.benchmark_returns:
            return None

        b_returns = context.benchmark_returns
        n = min(len(portfolio_returns), len(b_returns))
        if n < 2:
            return BenchmarkComparison(
                benchmark_name=context.benchmark_name,
                beta=1.0,
                alpha=0.0,
                correlation=0.0,
                benchmark_total_return=0.0,
                outperformance=portfolio_total_return,
            )

        p_ret = portfolio_returns[:n]
        b_ret = b_returns[:n]

        mean_p = sum(p_ret) / n
        mean_b = sum(b_ret) / n

        var_b = sum((b - mean_b) ** 2 for b in b_ret) / (n - 1)
        cov_pb = sum((p - mean_p) * (b - mean_b) for p, b in zip(p_ret, b_ret)) / (n - 1)

        beta = cov_pb / var_b if var_b > 0.0 else 1.0

        var_p = sum((p - mean_p) ** 2 for p in p_ret) / (n - 1)
        std_p = var_p ** 0.5
        std_b = var_b ** 0.5
        corr = cov_pb / (std_p * std_b) if (std_p * std_b) > 0.0 else 0.0

        # Benchmark cumulative return
        b_cum = 1.0
        for r in b_ret:
            b_cum *= (1.0 + r)
        b_total_ret = b_cum - 1.0

        annualized_p = mean_p * context.annualization_factor
        annualized_b = mean_b * context.annualization_factor
        alpha = annualized_p - (context.risk_free_rate + beta * (annualized_b - context.risk_free_rate))

        prec = context.decimal_precision

        return BenchmarkComparison(
            benchmark_name=context.benchmark_name,
            beta=round(beta, prec),
            alpha=round(alpha, prec),
            correlation=round(max(-1.0, min(1.0, corr)), prec),
            benchmark_total_return=round(b_total_ret, prec),
            outperformance=round(portfolio_total_return - b_total_ret, prec),
        )
