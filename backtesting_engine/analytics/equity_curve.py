"""Equity Curve Engine computing equity history, portfolio values, and return series (Sprint 8A-H)."""

from __future__ import annotations

from typing import List, Optional
from backtesting_engine.analytics.models.analytics import AnalyticsContext, EquityCurveAnalysis
from backtesting_engine.core.models import EquityPoint


class EquityCurveEngine:
    """Pure computational engine for equity curves, portfolio value history, and return series."""

    @staticmethod
    def calculate(
        snapshots: List[EquityPoint],
        initial_capital: float = 100000.0,
        context: Optional[AnalyticsContext] = None,
    ) -> EquityCurveAnalysis:
        """Compute equity history, portfolio values, periodic returns, and cumulative returns using AnalyticsContext."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        if not snapshots:
            base_eq = initial_capital if initial_capital > 0.0 else 1.0
            return EquityCurveAnalysis(
                equity_history=[base_eq],
                portfolio_value_history=[base_eq],
                daily_returns=[],
                cumulative_returns=[0.0],
            )

        eq_history: List[float] = []
        val_history: List[float] = []

        for p in snapshots:
            eq_history.append(float(p.equity))
            val_history.append(float(p.account_value))

        # Periodic returns computation: (E_t - E_{t-1}) / E_{t-1}
        daily_returns: List[float] = []
        for i in range(1, len(eq_history)):
            prev = eq_history[i - 1]
            curr = eq_history[i]
            if prev > 0.0:
                ret = (curr - prev) / prev
            else:
                ret = 0.0
            daily_returns.append(round(ret, prec + 4))

        # Cumulative returns computation: (E_t - E_initial) / E_initial
        base_cap = initial_capital if initial_capital > 0.0 else (eq_history[0] if eq_history[0] > 0.0 else 1.0)
        cum_returns: List[float] = []
        for eq in eq_history:
            cum_ret = (eq - base_cap) / base_cap
            cum_returns.append(round(cum_ret, prec + 4))

        return EquityCurveAnalysis(
            equity_history=eq_history,
            portfolio_value_history=val_history,
            daily_returns=daily_returns,
            cumulative_returns=cum_returns,
        )
