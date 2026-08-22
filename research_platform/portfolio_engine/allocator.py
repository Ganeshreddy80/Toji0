"""Allocator implementing basic equal weighting, inverse volatility, and Kelly sizing.
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone
from typing import List

from research_platform.portfolio_engine.interfaces import IPortfolioAllocator
from research_platform.portfolio_engine.models import AllocationResult, PortfolioWeights


class PortfolioAllocator(IPortfolioAllocator):
    """Allocates asset weights using non-optimized sizing methodologies."""

    def __init__(self, method: str = "equal") -> None:
        self.method = method

    def allocate(self, symbols: List[str], returns_df: pd.DataFrame) -> AllocationResult:
        """Allocate weights over symbols based on defined sizing logic."""
        n = len(symbols)
        if n == 0:
            return AllocationResult(
                allocator_name=self.method.upper(),
                weights=PortfolioWeights(weights={}, timestamp=datetime.now(timezone.utc)),
                total_allocated=0.0
            )

        weights_dict = {}

        if self.method == "equal":
            # Equal weight
            w = 1.0 / n
            weights_dict = {sym: w for sym in symbols}

        elif self.method == "inverse_vol" and not returns_df.empty:
            # Inverse volatility weights
            vols = returns_df[symbols].std()
            inv_vols = 1.0 / (vols + 1e-10)
            sum_inv_vols = inv_vols.sum()
            
            for sym in symbols:
                weights_dict[sym] = float(inv_vols[sym] / (sum_inv_vols + 1e-10))

        elif self.method == "kelly":
            # Kelly Criterion approximation: (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
            # For multiple assets, we approximate via expectation/variance sizing: E[R] / Var(R)
            means = returns_df[symbols].mean()
            vols = returns_df[symbols].std()
            raw_kelly = means / (vols ** 2 + 1e-10)
            
            # Bound Kelly fractions to positive values and scale
            positive_kelly = raw_kelly.clip(lower=0.0)
            sum_kelly = positive_kelly.sum()
            
            if sum_kelly > 0.0:
                for sym in symbols:
                    weights_dict[sym] = float(positive_kelly[sym] / sum_kelly)
            else:
                # Fallback to equal weighting
                w = 1.0 / n
                weights_dict = {sym: w for sym in symbols}

        else:
            # Fallback to equal weight
            w = 1.0 / n
            weights_dict = {sym: w for sym in symbols}

        return AllocationResult(
            allocator_name=self.method.upper(),
            weights=PortfolioWeights(weights=weights_dict, timestamp=datetime.now(timezone.utc)),
            total_allocated=sum(weights_dict.values())
        )
