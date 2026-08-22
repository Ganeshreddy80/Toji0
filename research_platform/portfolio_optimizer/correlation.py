"""Correlation matrix calculator engine implementing ICorrelationEngine.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List
from research_platform.portfolio_optimizer.interfaces import ICorrelationEngine
from research_platform.portfolio_optimizer.models import CorrelationMatrix

logger = logging.getLogger(__name__)


class CorrelationEngine(ICorrelationEngine):
    """Computes Pearson correlation coefficients across asset returns history."""

    def calculate_correlation(self, returns_data: Dict[str, List[float]]) -> CorrelationMatrix:
        """Calculate correlation matrix for strategy returns."""
        symbols = sorted(list(returns_data.keys()))
        n_symbols = len(symbols)

        if n_symbols == 0:
            return CorrelationMatrix(symbols=[], matrix=[])

        # Initialize matrix with 1.0 on diagonal, 0.0 off-diagonal
        matrix = [[1.0 if i == j else 0.0 for j in range(n_symbols)] for i in range(n_symbols)]

        # Get returns length
        sample_lens = [len(r) for r in returns_data.values()]
        min_len = min(sample_lens) if sample_lens else 0

        if min_len < 2:
            return CorrelationMatrix(symbols=symbols, matrix=matrix)

        # Precompute means and variances
        means = {}
        deviations = {}
        for s in symbols:
            ret = returns_data[s][:min_len]
            mean = sum(ret) / min_len
            means[s] = mean
            # Subtract mean
            dev = [r - mean for r in ret]
            deviations[s] = dev

        # Compute covariance and correlation pairs
        for i in range(n_symbols):
            for j in range(i + 1, n_symbols):
                s1 = symbols[i]
                s2 = symbols[j]
                
                dev1 = deviations[s1]
                dev2 = deviations[s2]

                num = sum(d1 * d2 for d1, d2 in zip(dev1, dev2))
                den1 = sum(d ** 2 for d in dev1)
                den2 = sum(d ** 2 for d in dev2)
                den = math.sqrt(den1 * den2)

                corr = num / den if den > 0.0 else 0.0
                # Clamp boundaries
                corr = min(max(corr, -1.0), 1.0)
                
                matrix[i][j] = corr
                matrix[j][i] = corr

        return CorrelationMatrix(symbols=symbols, matrix=matrix)
