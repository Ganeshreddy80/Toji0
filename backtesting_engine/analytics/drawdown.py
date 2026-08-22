"""Drawdown Engine computing drawdown curves, max drawdown, and peak/trough durations (Sprint 8A-H)."""

from __future__ import annotations

from typing import List, Optional
from backtesting_engine.analytics.models.analytics import AnalyticsContext, DrawdownMetrics
from backtesting_engine.core.models import EquityPoint


class DrawdownEngine:
    """Pure computational engine for peak-to-trough drawdown curves and duration tracking."""

    @staticmethod
    def calculate(
        snapshots: List[EquityPoint],
        initial_capital: float = 100000.0,
        context: Optional[AnalyticsContext] = None,
    ) -> DrawdownMetrics:
        """Compute drawdown curve, max drawdown, drawdown duration, and recovery duration using AnalyticsContext."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        if not snapshots:
            return DrawdownMetrics(
                drawdown_curve=[0.0],
                max_drawdown=0.0,
                max_drawdown_duration_seconds=0.0,
                max_recovery_duration_seconds=0.0,
                peak_equity=initial_capital,
                trough_equity=initial_capital,
            )

        hwm = max(initial_capital, snapshots[0].equity)
        drawdown_curve: List[float] = []

        max_dd = 0.0
        peak_eq = hwm
        trough_eq = hwm

        # Variables for tracking worst drawdown episode
        worst_dd_peak_idx = 0
        worst_dd_trough_idx = 0
        worst_dd_recovery_idx = -1

        current_peak_idx = 0
        current_peak_val = hwm

        for idx, point in enumerate(snapshots):
            eq = point.equity
            if eq > current_peak_val:
                current_peak_val = eq
                current_peak_idx = idx

            dd = (current_peak_val - eq) / current_peak_val if current_peak_val > 0.0 else 0.0
            dd_bounded = max(0.0, min(1.0, dd))
            drawdown_curve.append(round(dd_bounded, prec + 4))

            if dd_bounded > max_dd:
                max_dd = dd_bounded
                worst_dd_peak_idx = current_peak_idx
                worst_dd_trough_idx = idx
                peak_eq = current_peak_val
                trough_eq = eq

        # If max drawdown > 0, find recovery index
        if max_dd > 0.0:
            for idx in range(worst_dd_trough_idx + 1, len(snapshots)):
                if snapshots[idx].equity >= peak_eq:
                    worst_dd_recovery_idx = idx
                    break

        # Calculate time durations in seconds using timestamps if available
        dd_duration_sec = 0.0
        rec_duration_sec = 0.0

        if snapshots and max_dd > 0.0:
            peak_ts = snapshots[worst_dd_peak_idx].timestamp
            trough_ts = snapshots[worst_dd_trough_idx].timestamp
            dd_duration_sec = max(0.0, (trough_ts - peak_ts).total_seconds())

            if worst_dd_recovery_idx != -1:
                rec_ts = snapshots[worst_dd_recovery_idx].timestamp
                rec_duration_sec = max(0.0, (rec_ts - trough_ts).total_seconds())

        return DrawdownMetrics(
            drawdown_curve=drawdown_curve,
            max_drawdown=round(max_dd, prec),
            max_drawdown_duration_seconds=dd_duration_sec,
            max_recovery_duration_seconds=rec_duration_sec,
            peak_equity=round(peak_eq, prec),
            trough_equity=round(trough_eq, prec),
        )
