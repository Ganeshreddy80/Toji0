"""Advanced portfolio analytics calculator.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


class AdvancedPortfolioAnalytics:
    """Calculates advanced trading performance and risk metrics from trade history."""

    @staticmethod
    def calculate_metrics(
        initial_capital: float,
        pnls: List[float],
        risk_free_rate: float = 0.0
    ) -> Dict[str, Any]:
        """Compute advanced analytics metrics from a list of sequential trade PnLs."""
        if not pnls:
            return {
                "equity_curve": [initial_capital],
                "profit_factor": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "rolling_sharpe": 0.0,
                "rolling_sortino": 0.0,
                "max_drawdown": 0.0
            }

        # 1. Equity Curve
        equity_curve = [initial_capital]
        current_equity = initial_capital
        peak = initial_capital
        max_dd = 0.0

        for pnl in pnls:
            current_equity += pnl
            equity_curve.append(current_equity)
            if current_equity > peak:
                peak = current_equity
            dd = (peak - current_equity) / peak
            if dd > max_dd:
                max_dd = dd

        # 2. Profit Factor
        gross_profits = sum(p for p in pnls if p > 0)
        gross_losses = sum(abs(p) for p in pnls if p < 0)
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 0.0)

        # 3. Win Rate
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls) if pnls else 0.0

        # Calculate percentage returns for Sharpe / Sortino
        returns = []
        prev = initial_capital
        for eq in equity_curve[1:]:
            ret = (eq - prev) / prev
            returns.append(ret)
            prev = eq

        # 4. Rolling Sharpe and Sortino
        sharpe = 0.0
        sortino = 0.0

        if returns:
            n = len(returns)
            mean_ret = sum(returns) / n
            excess_ret = [r - (risk_free_rate / 252.0) for r in returns]
            mean_excess = sum(excess_ret) / n

            # Standard deviation of returns
            variance = sum((r - mean_ret) ** 2 for r in returns) / n
            std_dev = math.sqrt(variance) if variance > 0 else 0.0

            if std_dev > 0.0:
                # Annualized Sharpe (assuming daily returns: multiply by sqrt(252))
                sharpe = (mean_excess / std_dev) * math.sqrt(252.0)

            # Downside standard deviation (only returns < risk_free_rate)
            downside_returns = [r for r in returns if r < 0.0]
            if downside_returns:
                downside_variance = sum(r ** 2 for r in downside_returns) / n
                downside_std = math.sqrt(downside_variance)
                if downside_std > 0.0:
                    sortino = (mean_excess / downside_std) * math.sqrt(252.0)
            else:
                sortino = sharpe

        return {
            "equity_curve": equity_curve,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": len(pnls),
            "rolling_sharpe": sharpe,
            "rolling_sortino": sortino,
            "max_drawdown": max_dd
        }
