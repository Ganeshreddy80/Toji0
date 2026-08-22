"""Market Regime classification engine.
"""

from __future__ import annotations

import math
import numpy as np
from typing import Dict, List

from research_platform.validation_core.models import RegimeValidationResult


class MarketRegimeClassifier:
    """Labels segments of return histories with market state regimes (Trending, Mean Reverting, Volatile)."""

    @staticmethod
    def classify_regimes(returns: np.ndarray, window: int = 20) -> List[str]:
        """Classify each point of the returns array into market state regimes.

        Returns:
            List of labels: ['trending', 'mean_reverting', 'volatile', 'sideways', etc.]
        """
        N = len(returns)
        labels = []
        
        # Calculate rolling variance and absolute returns
        for i in range(N):
            if i < window:
                labels.append("sideways")
                continue
            
            sub = returns[i - window + 1: i + 1]
            vol = float(np.std(sub))
            mean_ret = float(np.mean(sub))
            
            # Simple heuristics
            if vol > 0.02:  # High standard deviation
                labels.append("volatile")
            elif abs(mean_ret) > 0.005:  # Absolute trend direction
                labels.append("trending")
            else:
                # check autocorrelation lag 1 for mean reversion
                mean_sub = np.mean(sub)
                shifted = sub[:-1] - mean_sub
                original = sub[1:] - mean_sub
                cov = np.sum(shifted * original) / (window - 1)
                var = np.var(sub) + 1e-10
                r1 = cov / var
                if r1 < -0.15:
                    labels.append("mean_reverting")
                else:
                    labels.append("sideways")

        return labels

    @classmethod
    def evaluate_regimes(cls, returns: np.ndarray, pnl_series: np.ndarray) -> List[RegimeValidationResult]:
        """Group trading performance metrics by classified market regime blocks."""
        N = len(returns)
        if N != len(pnl_series):
            return []

        regimes = cls.classify_regimes(returns)
        regime_pnls: Dict[str, List[float]] = {}
        
        for r, pnl in zip(regimes, pnl_series):
            if r not in regime_pnls:
                regime_pnls[r] = []
            regime_pnls[r].append(pnl)

        results = []
        for name, pnls in regime_pnls.items():
            if len(pnls) < 4:
                continue
            
            # Calculate simple Sharpe of changes
            changes = np.diff(pnls)
            mean_change = np.mean(changes) if len(changes) > 0 else 0.0
            std_change = np.std(changes) if len(changes) > 0 else 1.0
            sr = mean_change / (std_change + 1e-10) * math.sqrt(252.0)
            
            # Drawdown
            peaks = np.maximum.accumulate(pnls)
            drawdowns = (peaks - pnls) / (peaks + 1e-10)
            max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

            results.append(
                RegimeValidationResult(
                    regime_name=name,
                    sharpe=float(sr),
                    total_samples=len(pnls),
                    max_drawdown=max_dd
                )
            )
        return results
