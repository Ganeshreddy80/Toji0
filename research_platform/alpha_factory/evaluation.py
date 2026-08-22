"""Evaluation engine computing Rank IC, turnover, capacity, and exposures.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from typing import Dict

from research_platform.alpha_factory.models import AlphaMetrics


class AlphaEvaluator:
    """Computes multi-dimensional statistical performance metrics for alphas."""

    @staticmethod
    def evaluate(
        signal: pd.Series,
        forward_returns: pd.Series,
        volume: pd.Series,
        ast_complexity: int
    ) -> AlphaMetrics:
        """Compute performance indicators for the alpha candidate."""
        df = pd.concat([signal, forward_returns, volume], axis=1).dropna()
        df.columns = ["signal", "returns", "volume"]

        if len(df) < 10:
            return AlphaMetrics(
                rank_ic=0.0,
                ic_stability=0.0,
                turnover=1.0,
                capacity=0.0,
                mutual_info=0.0,
                complexity=ast_complexity,
                sharpe=0.0,
                drawdown=0.0
            )

        # 1. Rank IC (Spearman correlation calculated via Pearson on ranks)
        rank_ic = float(df["signal"].rank().corr(df["returns"].rank(), method="pearson"))
        if np.isnan(rank_ic):
            rank_ic = 0.0

        # 2. IC Stability (mean rolling IC / std rolling IC)
        rolling_ics = []
        window = min(len(df) // 4, 30)
        window = max(window, 5)
        for i in range(len(df) - window + 1):
            sub = df.iloc[i : i + window]
            ic = sub["signal"].rank().corr(sub["returns"].rank(), method="pearson")
            if not np.isnan(ic):
                rolling_ics.append(ic)

        mean_ic = np.mean(rolling_ics) if rolling_ics else 0.0
        std_ic = np.std(rolling_ics) if rolling_ics else 1.0
        ic_stability = float(mean_ic / (std_ic + 1e-10))

        # 3. Signal Turnover: sum(|signal_t - signal_{t-1}|)
        signal_diff = df["signal"].diff().abs()
        # Scale to average daily turnover (0.0 to 2.0 where 2.0 is complete reversal)
        turnover = float(signal_diff.mean()) if not np.isnan(signal_diff.mean()) else 0.0

        # 4. Capacity (heuristic based on ADV and turnover)
        # Capacity = ADV * 0.01 / (turnover + 0.01)
        mean_adv = float(df["volume"].mean())
        capacity = float(mean_adv * 0.01 / (turnover + 0.01))

        # 5. Mutual Information
        mi = AlphaEvaluator._calculate_mutual_information(df["signal"].values, df["returns"].values)

        # 6. Simple Sharpe
        mean_ret = float(df["returns"].mean())
        std_ret = float(df["returns"].std())
        sharpe = mean_ret / (std_ret + 1e-10) * math.sqrt(252)

        # Drawdown
        pnl = np.cumsum(df["returns"].values)
        peaks = np.maximum.accumulate(pnl)
        drawdowns = (peaks - pnl) / (peaks + 1e-10)
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        return AlphaMetrics(
            rank_ic=rank_ic,
            ic_stability=ic_stability,
            turnover=turnover,
            capacity=capacity,
            mutual_info=mi,
            complexity=ast_complexity,
            sharpe=sharpe,
            drawdown=max_dd
        )

    @staticmethod
    def _calculate_mutual_information(X: np.ndarray, Y: np.ndarray, bins: int = 10) -> float:
        """Calculate Mutual Information using 2D histogram binning."""
        try:
            joint_hist, _, _ = np.histogram2d(X, Y, bins=bins)
            total = np.sum(joint_hist)
            if total == 0:
                return 0.0

            p_xy = joint_hist / total
            p_x = np.sum(p_xy, axis=1, keepdims=True)
            p_y = np.sum(p_xy, axis=0, keepdims=True)

            mi = 0.0
            for i in range(bins):
                for j in range(bins):
                    pxy = p_xy[i, j]
                    px = p_x[i, 0]
                    py = p_y[0, j]
                    if pxy > 0 and px > 0 and py > 0:
                        mi += pxy * math.log(pxy / (px * py))
            return max(mi, 0.0)
        except Exception:
            return 0.0
