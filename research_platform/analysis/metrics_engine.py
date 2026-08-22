"""Deterministic quantitative performance and risk metrics engine (Sprint 6)."""

from __future__ import annotations

import math
from typing import List, Optional

from research_platform.core.interfaces import IMetricsEngine
from research_platform.core.models import PerformanceMetrics


class MetricsEngine(IMetricsEngine):
    """Calculates deterministic performance and risk metrics without executing trades."""

    def calculate_metrics(
        self, returns: List[float], equity_curve: Optional[List[float]] = None, risk_free_rate: float = 0.0
    ) -> PerformanceMetrics:
        """Calculate deterministic performance metrics from periodic return series or equity curve."""
        if not returns and not equity_curve:
            return PerformanceMetrics()

        # Generate returns from equity curve if returns list is empty
        if not returns and equity_curve and len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev = equity_curve[i - 1]
                curr = equity_curve[i]
                r = (curr - prev) / prev if prev > 0.0 else 0.0
                returns.append(r)

        if not returns:
            return PerformanceMetrics()

        n = len(returns)
        total_trades = n
        winning_trades = sum(1 for r in returns if r > 0.0)
        losing_trades = sum(1 for r in returns if r < 0.0)
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0

        gross_profit = sum(r for r in returns if r > 0.0)
        gross_loss = abs(sum(r for r in returns if r < 0.0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0.0 else (gross_profit if gross_profit > 0.0 else 0.0)

        mean_return = sum(returns) / n
        expected_return = mean_return

        # Variance & Volatility
        variance = sum((r - mean_return) ** 2 for r in returns) / n if n > 1 else 0.0
        stdev = math.sqrt(variance)
        annualized_volatility = stdev * math.sqrt(252.0)

        # Excess return for Sharpe
        excess_mean = mean_return - (risk_free_rate / 252.0)
        sharpe_ratio = (excess_mean / stdev * math.sqrt(252.0)) if stdev > 0.0 else 0.0

        # Downside Deviation for Sortino
        downside_sq = [min(0.0, r - (risk_free_rate / 252.0)) ** 2 for r in returns]
        downside_dev = math.sqrt(sum(downside_sq) / n) if n > 0 else 0.0
        sortino_ratio = (excess_mean / downside_dev * math.sqrt(252.0)) if downside_dev > 0.0 else 0.0

        # Max Drawdown & Equity Curve calculation
        if not equity_curve:
            eq = [1.0]
            for r in returns:
                eq.append(eq[-1] * (1.0 + r))
            equity_curve = eq

        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0.0 else 0.0
            if dd > max_dd:
                max_dd = dd

        # CAGR
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0] if equity_curve[0] > 0.0 else 0.0
        years = n / 252.0 if n > 0 else 1.0
        cagr = ((1.0 + total_return) ** (1.0 / years) - 1.0) if (years > 0.0 and (1.0 + total_return) > 0.0) else total_return

        calmar_ratio = (cagr / max_dd) if max_dd > 0.0 else 0.0

        # Value at Risk 95% (Parametric & Historical lower bound)
        sorted_returns = sorted(returns)
        var_index = int(0.05 * n)
        value_at_risk_95 = abs(sorted_returns[var_index]) if sorted_returns and var_index < n else 0.0

        # Tail Risk / CVaR 95%
        tail_returns = sorted_returns[: max(1, var_index)]
        tail_risk = abs(sum(tail_returns) / len(tail_returns)) if tail_returns else value_at_risk_95

        return PerformanceMetrics(
            sharpe_ratio=round(sharpe_ratio, 4),
            sortino_ratio=round(sortino_ratio, 4),
            max_drawdown=round(max_dd, 4),
            calmar_ratio=round(calmar_ratio, 4),
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 4),
            cagr=round(cagr, 4),
            annualized_volatility=round(annualized_volatility, 4),
            expected_return=round(expected_return, 6),
            value_at_risk_95=round(value_at_risk_95, 6),
            tail_risk=round(tail_risk, 6),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )
