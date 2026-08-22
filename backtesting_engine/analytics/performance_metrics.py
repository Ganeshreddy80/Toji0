"""Performance Metrics Engine computing Total Return, CAGR, Annualized Return, and Volatility (Sprint 8A-H)."""

from __future__ import annotations

import math
from typing import List, Optional

from backtesting_engine.analytics.models.analytics import AnalyticsContext, PerformanceMetrics
from backtesting_engine.core.models import EquityPoint


class PerformanceMetricsEngine:
    """Pure computational engine for portfolio return performance metrics driven by AnalyticsContext."""

    @staticmethod
    def calculate(
        snapshots: List[EquityPoint],
        daily_returns: List[float],
        initial_capital: float = 100000.0,
        context: Optional[AnalyticsContext] = None,
    ) -> PerformanceMetrics:
        """Calculate Total Return, CAGR, Annualized Return, and Volatility using AnalyticsContext parameters."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        if not snapshots:
            return PerformanceMetrics(
                total_return=0.0,
                cagr=0.0,
                annualized_return=0.0,
                volatility=0.0,
            )

        start_eq = initial_capital if initial_capital > 0.0 else snapshots[0].equity
        final_eq = snapshots[-1].equity

        # 1. Total Return
        total_return = (final_eq - start_eq) / start_eq if start_eq > 0.0 else 0.0

        # 2. CAGR (Compound Annual Growth Rate) using ctx.trading_days instead of magic numbers
        cagr = 0.0
        if len(snapshots) >= 2 and start_eq > 0.0 and final_eq > 0.0:
            start_time = snapshots[0].timestamp
            end_time = snapshots[-1].timestamp
            total_seconds = (end_time - start_time).total_seconds()
            total_days = total_seconds / 86400.0

            if total_days > 0.0:
                years = total_days / ctx.trading_days
                try:
                    cagr = (final_eq / start_eq) ** (1.0 / years) - 1.0
                except (ValueError, ZeroDivisionError, OverflowError):
                    cagr = 0.0

        # 3. Annualized Return & Volatility using ctx.annualization_factor
        annualized_return = 0.0
        volatility = 0.0

        if daily_returns:
            n = len(daily_returns)
            mean_ret = sum(daily_returns) / n
            annualized_return = mean_ret * ctx.annualization_factor

            if n >= 2:
                variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)
                sample_std = math.sqrt(variance)
                volatility = sample_std * math.sqrt(ctx.annualization_factor)

        return PerformanceMetrics(
            total_return=round(total_return, prec),
            cagr=round(cagr, prec),
            annualized_return=round(annualized_return, prec),
            volatility=round(volatility, prec),
        )
