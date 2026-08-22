"""Performance engine computing net returns, CAGRs, and peak-to-trough drawdowns.
"""

from __future__ import annotations

import math
from typing import List
from research_platform.portfolio_analytics.interfaces import IPerformanceEngine
from research_platform.portfolio_analytics.models import PortfolioReturn, DrawdownAnalysis


class PerformanceEngine(IPerformanceEngine):
    """Calculates returns, rolling equity distributions, and drawdown durations."""

    def calculate_returns(self, nav_series: List[float], initial_nav: float) -> PortfolioReturn:
        if not nav_series or initial_nav <= 0.0:
            return PortfolioReturn(total_return=0.0, net_return=0.0, gross_return=0.0, cagr=0.0)

        final_nav = nav_series[-1]
        gross = (final_nav - initial_nav) / initial_nav
        net = gross

        # Annualized CAGR assuming 252 trading days per year
        days = len(nav_series)
        years = days / 252.0
        if years > 0.0 and final_nav > 0.0 and initial_nav > 0.0:
            try:
                cagr = (final_nav / initial_nav) ** (1.0 / years) - 1.0
            except Exception:
                cagr = gross
        else:
            cagr = gross

        return PortfolioReturn(
            total_return=gross,
            net_return=net,
            gross_return=gross,
            cagr=cagr
        )

    def calculate_drawdown(self, nav_series: List[float]) -> DrawdownAnalysis:
        if not nav_series:
            return DrawdownAnalysis(max_drawdown=0.0, recovery_time_sec=0.0, drawdown_duration_sec=0.0)

        peak = nav_series[0]
        max_dd = 0.0
        
        peak_idx = 0
        max_dd_duration = 0
        current_dd_duration = 0
        recovery_time = 0

        for idx, nav in enumerate(nav_series):
            if nav > peak:
                peak = nav
                peak_idx = idx
                current_dd_duration = 0
            else:
                dd = (peak - nav) / peak
                if dd > max_dd:
                    max_dd = dd
                current_dd_duration = idx - peak_idx
                max_dd_duration = max(max_dd_duration, current_dd_duration)

        # Estimate durations in seconds (assuming 1 hour/3600s per tick step)
        return DrawdownAnalysis(
            max_drawdown=max_dd,
            recovery_time_sec=float(current_dd_duration * 3600),
            drawdown_duration_sec=float(max_dd_duration * 3600)
        )
