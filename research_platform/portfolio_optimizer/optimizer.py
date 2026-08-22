"""Portfolio optimization solver implementing IPortfolioOptimizationEngine.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Tuple
from research_platform.portfolio_optimizer.interfaces import IPortfolioOptimizationEngine
from research_platform.portfolio_optimizer.models import OptimizerResult

logger = logging.getLogger(__name__)


class PortfolioOptimizationEngine(IPortfolioOptimizationEngine):
    """Solves mathematical portfolio allocations (Mean-Variance and Risk Parity benchmarks)."""

    def _compute_covariance(self, returns_data: Dict[str, List[float]], symbols: List[str]) -> Tuple[List[float], List[List[float]]]:
        """Compute mean returns vector and covariance matrix."""
        n = len(symbols)
        means = []
        deviations = {}
        
        # Get minimum sample size
        min_len = min(len(returns_data[s]) for s in symbols)

        for s in symbols:
            ret = returns_data[s][:min_len]
            mean = sum(ret) / min_len
            means.append(mean)
            deviations[s] = [r - mean for r in ret]

        covariance = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dev1 = deviations[symbols[i]]
                dev2 = deviations[symbols[j]]
                cov = sum(d1 * d2 for d1, d2 in zip(dev1, dev2)) / (min_len - 1)
                covariance[i][j] = cov

        return means, covariance

    def optimize_portfolio(
        self,
        symbols: List[str],
        returns_data: Dict[str, List[float]],
        target_risk: float = 0.5,
        min_weight: float = 0.0,
        max_weight: float = 1.0
    ) -> OptimizerResult:
        """Calculate optimal weights using Inverse-Variance optimization."""
        n_symbols = len(symbols)
        if n_symbols == 0:
            return OptimizerResult(weights={}, expected_return=0.0, expected_volatility=0.0, sharpe_ratio=0.0)

        if n_symbols == 1:
            sym = symbols[0]
            ret = returns_data[sym]
            mean_ret = sum(ret) / len(ret) if ret else 0.0
            vol = math.sqrt(sum((r - mean_ret)**2 for r in ret) / (len(ret) - 1)) if len(ret) > 1 else 0.0
            sharpe = mean_ret / vol if vol > 0 else 0.0
            return OptimizerResult(
                weights={sym: 1.0},
                expected_return=mean_ret,
                expected_volatility=vol,
                sharpe_ratio=sharpe
            )

        # Compute inputs
        means, covariance = self._compute_covariance(returns_data, symbols)

        # 1. Inverse-Variance weighting (Risk Parity approximation)
        inv_variances = []
        for i in range(n_symbols):
            var = covariance[i][i]
            # Avoid division by zero
            inv_var = 1.0 / var if var > 0.000001 else 1.0
            inv_variances.append(inv_var)

        total_inv_var = sum(inv_variances)
        weights = {}
        for i, sym in enumerate(symbols):
            w = inv_variances[i] / total_inv_var if total_inv_var > 0 else 1.0 / n_symbols
            # Clamp limits
            w = min(max(w, min_weight), max_weight)
            weights[sym] = w

        # Normalize weights to sum to 1
        sum_w = sum(weights.values())
        if sum_w > 0:
            weights = {s: w / sum_w for s, w in weights.items()}

        # 2. Compute expected return and volatility of the optimized portfolio
        w_vec = [weights[s] for s in symbols]
        portfolio_return = sum(w_vec[i] * means[i] for i in range(n_symbols))

        # Volatility = sqrt(w^T * Σ * w)
        sigma_w = [0.0] * n_symbols
        for i in range(n_symbols):
            for j in range(n_symbols):
                sigma_w[i] += covariance[i][j] * w_vec[j]

        portfolio_var = sum(w_vec[i] * sigma_w[i] for i in range(n_symbols))
        portfolio_vol = math.sqrt(portfolio_var) if portfolio_var > 0 else 0.0

        # Sharpe Ratio (assumes risk-free rate is 0.0)
        sharpe = portfolio_return / portfolio_vol if portfolio_vol > 0 else 0.0

        return OptimizerResult(
            weights=weights,
            expected_return=portfolio_return,
            expected_volatility=portfolio_vol,
            sharpe_ratio=sharpe
        )
