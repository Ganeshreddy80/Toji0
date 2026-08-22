"""Performance Attribution engine implementing Brinson-Fachler models.
"""

from __future__ import annotations

from typing import Dict

from research_platform.portfolio_engine.interfaces import IPerformanceAttribution
from research_platform.portfolio_engine.models import (
    PortfolioPerformance,
    PortfolioStatistics,
    PortfolioWeights
)


class BrinsonAttribution(IPerformanceAttribution):
    """Calculates allocation, selection, and interaction effects against benchmark weights."""

    def calculate_attribution(
        self,
        portfolio_weights: PortfolioWeights,
        benchmark_weights: PortfolioWeights,
        portfolio_returns: Dict[str, float],
        benchmark_returns: Dict[str, float]
    ) -> PortfolioPerformance:
        """Calculate Brinson-Fachler attribution effects.

        Formula:
            Allocation Effect = (w_p - w_b) * (R_b - R_b_total)
            Selection Effect = w_b * (R_p - R_b)
        """
        all_symbols = set(portfolio_weights.weights.keys()).union(benchmark_weights.weights.keys())

        # 1. Total benchmark return
        r_b_total = sum(benchmark_weights.weights.get(sym, 0.0) * benchmark_returns.get(sym, 0.0) for sym in all_symbols)

        allocation_effect = {}
        selection_effect = {}
        total_attrib = 0.0

        for sym in all_symbols:
            w_p = portfolio_weights.weights.get(sym, 0.0)
            w_b = benchmark_weights.weights.get(sym, 0.0)
            r_p = portfolio_returns.get(sym, 0.0)
            r_b = benchmark_returns.get(sym, 0.0)

            # Allocation Effect
            alloc = (w_p - w_b) * (r_b - r_b_total)
            # Selection Effect
            select = w_b * (r_p - r_b)

            allocation_effect[sym] = alloc
            selection_effect[sym] = select
            total_attrib += (alloc + select)

        stats = PortfolioStatistics(
            cagr=total_attrib,
            volatility=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0
        )

        return PortfolioPerformance(
            statistics=stats,
            allocation_effect=allocation_effect,
            selection_effect=selection_effect,
            total_attribution=total_attrib
        )
