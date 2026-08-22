"""Trade Statistics Engine computing trade counts, win rate, expectancy, and holding times (Sprint 8A-H)."""

from __future__ import annotations

from typing import List, Optional
from backtesting_engine.analytics.models.analytics import AnalyticsContext, TradeStatistics
from backtesting_engine.core.models import TradeRecord


class TradeStatisticsEngine:
    """Pure computational engine for trade execution, PnL, and duration statistics."""

    @staticmethod
    def calculate(
        trades: List[TradeRecord],
        context: Optional[AnalyticsContext] = None,
    ) -> TradeStatistics:
        """Calculate complete trade execution and PnL metrics using AnalyticsContext."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        if not trades:
            return TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                even_trades=0,
                win_rate=0.0,
                average_winner=0.0,
                average_loser=0.0,
                largest_winner=0.0,
                largest_loser=0.0,
                profit_factor=0.0,
                expectancy=0.0,
                average_holding_time_seconds=0.0,
            )

        total_trades = len(trades)
        winning_pnls = [t.realized_pnl for t in trades if t.realized_pnl > 0.0]
        losing_pnls = [t.realized_pnl for t in trades if t.realized_pnl < 0.0]
        even_count = sum(1 for t in trades if t.realized_pnl == 0.0)

        winning_trades = len(winning_pnls)
        losing_trades = len(losing_pnls)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        avg_winner = sum(winning_pnls) / winning_trades if winning_trades > 0 else 0.0
        avg_loser = sum(losing_pnls) / losing_trades if losing_trades > 0 else 0.0

        largest_winner = max(winning_pnls) if winning_trades > 0 else 0.0
        largest_loser = min(losing_pnls) if losing_trades > 0 else 0.0

        gross_profit = sum(winning_pnls)
        gross_loss = abs(sum(losing_pnls))

        if gross_loss > 0.0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = gross_profit if gross_profit > 0.0 else 0.0

        total_realized_pnl = sum(t.realized_pnl for t in trades)
        expectancy = total_realized_pnl / total_trades if total_trades > 0 else 0.0

        # Holding duration calculation for closed trades
        closed_durations: List[float] = []
        for t in trades:
            if t.closed_at and t.opened_at:
                duration = (t.closed_at - t.opened_at).total_seconds()
                if duration >= 0.0:
                    closed_durations.append(duration)

        avg_holding_sec = sum(closed_durations) / len(closed_durations) if closed_durations else 0.0

        return TradeStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            even_trades=even_count,
            win_rate=round(win_rate, prec),
            average_winner=round(avg_winner, prec),
            average_loser=round(avg_loser, prec),
            largest_winner=round(largest_winner, prec),
            largest_loser=round(largest_loser, prec),
            profit_factor=round(profit_factor, prec),
            expectancy=round(expectancy, prec),
            average_holding_time_seconds=round(avg_holding_sec, 2),
        )
