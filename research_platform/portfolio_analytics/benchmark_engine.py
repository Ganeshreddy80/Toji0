"""Benchmark comparison engine calculating Alpha, Beta, and relative performance ratios.
"""

from __future__ import annotations

import math
from typing import Dict, List
from research_platform.portfolio_analytics.interfaces import IBenchmarkEngine
from research_platform.portfolio_analytics.models import BenchmarkComparison


class BenchmarkEngine(IBenchmarkEngine):
    """Evaluates relative return statistics against benchmarks (BTC, ETH, baskets)."""

    def compare_benchmarks(self, portfolio_returns: List[float], benchmark_returns: Dict[str, List[float]]) -> List[BenchmarkComparison]:
        if not portfolio_returns:
            return []

        comparisons: List[BenchmarkComparison] = []
        p_total = sum(portfolio_returns)
        p_avg = p_total / len(portfolio_returns)
        
        # Calculate portfolio variance
        p_var = sum((r - p_avg) ** 2 for r in portfolio_returns) / len(portfolio_returns)
        
        for name, b_series in benchmark_returns.items():
            if not b_series:
                continue
            
            # Align lengths
            length = min(len(portfolio_returns), len(b_series))
            p_aligned = portfolio_returns[:length]
            b_aligned = b_series[:length]

            b_total = sum(b_aligned)
            b_avg = b_total / length
            b_var = sum((r - b_avg) ** 2 for r in b_aligned) / length

            # Covariance
            covar = sum((p_aligned[i] - p_avg) * (b_aligned[i] - b_avg) for i in range(length)) / length

            # Beta
            beta = covar / b_var if b_var > 0.0 else 1.0

            # Alpha (assuming risk free = 0.0)
            alpha = p_avg - (beta * b_avg)

            # Tracking error (standard dev of excess returns)
            excess = [p_aligned[i] - b_aligned[i] for i in range(length)]
            ex_avg = sum(excess) / length
            ex_var = sum((e - ex_avg) ** 2 for e in excess) / length
            tracking_error = math.sqrt(ex_var) if ex_var > 0.0 else 0.001

            # Information ratio
            info_ratio = ex_avg / tracking_error if tracking_error > 0.0 else 0.0

            # Capture ratio (relative absolute average)
            capture = p_avg / b_avg if b_avg != 0.0 else 1.0

            # Correlation
            p_std = math.sqrt(p_var) if p_var > 0.0 else 1.0
            b_std = math.sqrt(b_var) if b_var > 0.0 else 1.0
            correlation = covar / (p_std * b_std) if (p_std * b_std) > 0.0 else 1.0

            comparisons.append(BenchmarkComparison(
                benchmark_name=name,
                alpha=alpha,
                beta=beta,
                tracking_error=tracking_error,
                information_ratio=info_ratio,
                capture_ratio=capture,
                correlation=correlation,
                relative_return=p_total - b_total
            ))

        return comparisons
