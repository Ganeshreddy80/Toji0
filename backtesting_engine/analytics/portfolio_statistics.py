"""Portfolio Statistics Engine computing exposure, cash allocation, and turnover ratios (Sprint 8A-H)."""

from __future__ import annotations

from typing import List, Optional
from backtesting_engine.analytics.models.analytics import AnalyticsContext, PortfolioStatistics
from backtesting_engine.core.models import EquityPoint, SimulatedFill


class PortfolioStatisticsEngine:
    """Pure computational engine for portfolio exposure, cash percentage, and turnover."""

    @staticmethod
    def calculate(
        snapshots: List[EquityPoint],
        fills: List[SimulatedFill],
        initial_capital: float = 100000.0,
        context: Optional[AnalyticsContext] = None,
    ) -> PortfolioStatistics:
        """Calculate portfolio exposure ratio, cash percentage, invested percentage, and turnover using AnalyticsContext."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        if not snapshots:
            return PortfolioStatistics(
                exposure_ratio=0.0,
                cash_pct=1.0,
                invested_pct=0.0,
                turnover=0.0,
            )

        cash_ratios: List[float] = []
        invested_ratios: List[float] = []

        for p in snapshots:
            eq = p.equity
            if eq > 0.0:
                c_pct = max(0.0, min(1.0, p.balance / eq))
                inv_val = abs(p.account_value - p.balance) if p.account_value != 0.0 else (p.open_pnl if p.open_pnl != 0.0 else 0.0)
                inv_pct = max(0.0, min(1.0, inv_val / eq))
            else:
                c_pct = 1.0
                inv_pct = 0.0

            cash_ratios.append(c_pct)
            invested_ratios.append(inv_pct)

        n = len(snapshots)
        avg_cash = sum(cash_ratios) / n if n > 0 else 1.0
        avg_invested = sum(invested_ratios) / n if n > 0 else 0.0
        exposure_ratio = avg_invested

        # Turnover calculation: Total traded dollar volume / initial capital
        total_traded_val = sum(f.fill_quantity * f.fill_price for f in fills)
        base_cap = initial_capital if initial_capital > 0.0 else 1.0
        turnover = total_traded_val / base_cap

        return PortfolioStatistics(
            exposure_ratio=round(exposure_ratio, prec),
            cash_pct=round(avg_cash, prec),
            invested_pct=round(avg_invested, prec),
            turnover=round(turnover, prec),
        )
