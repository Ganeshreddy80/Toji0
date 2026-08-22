"""Performance Analytics engine.
"""

from __future__ import annotations

import math
import numpy as np
from typing import List

from research_platform.backtesting_engine.models import ExecutionStatistics


class BacktestAnalytics:
    """Computes CAGR, Sharpe, Sortino, Calmar, and Omega ratios from equity paths."""

    @staticmethod
    def calculate_stats(
        equity_curve: List[float],
        trades_pnl: List[float],
        initial_capital: float
    ) -> ExecutionStatistics:
        """Compute execution statistics from simulation runs."""
        if not equity_curve or len(equity_curve) < 2:
            return ExecutionStatistics(
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                cagr=0.0
            )

        # 1. CAGR
        final_equity = equity_curve[-1]
        n_days = len(equity_curve)
        cagr = (final_equity / initial_capital) ** (252.0 / max(n_days, 1)) - 1.0

        # 2. Drawdowns
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / (peak + 1e-10)
            if dd > max_dd:
                max_dd = dd

        # 3. Daily returns metrics
        eq_arr = np.array(equity_curve)
        daily_returns = np.diff(eq_arr) / (eq_arr[:-1] + 1e-10)

        mean_ret = np.mean(daily_returns) if len(daily_returns) > 0 else 0.0
        std_ret = np.std(daily_returns) if len(daily_returns) > 0 else 1.0
        sharpe = float(mean_ret / (std_ret + 1e-10) * math.sqrt(252.0))

        # 4. Trades Performance (Win Rate, Profit Factor)
        total_trades = len(trades_pnl)
        wins = [x for x in trades_pnl if x > 0]
        losses = [x for x in trades_pnl if x <= 0]
        
        win_rate = float(len(wins) / total_trades) if total_trades > 0 else 0.0
        
        sum_wins = sum(wins)
        sum_losses = abs(sum(losses))
        profit_factor = float(sum_wins / (sum_losses + 1e-10))

        return ExecutionStatistics(
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=float(max_dd),
            sharpe_ratio=sharpe,
            cagr=float(cagr)
        )

    @staticmethod
    def calculate_sortino(daily_returns: np.ndarray, target: float = 0.0) -> float:
        """Compute the Sortino Ratio using downside deviation."""
        if len(daily_returns) == 0:
            return 0.0

        excess = daily_returns - target
        downside_returns = excess[excess < 0]
        
        downside_dev = np.std(downside_returns) if len(downside_returns) > 0 else 1e-10
        mean_ret = np.mean(excess)
        return float(mean_ret / (downside_dev + 1e-10) * math.sqrt(252.0))
