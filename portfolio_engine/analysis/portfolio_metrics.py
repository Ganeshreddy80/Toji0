from __future__ import annotations

from typing import List
from portfolio_engine.core.models import ClosedPosition, PortfolioStatistics


class PortfolioMetricsCalculator:
    """Calculates statistics and performance ratios for closed historical positions."""

    @staticmethod
    def calculate_statistics(closed_positions: List[ClosedPosition]) -> PortfolioStatistics:
        """Aggregate closed position results into comprehensive statistics."""
        total = len(closed_positions)
        if total == 0:
            return PortfolioStatistics(
                winning_pct=0.0,
                losing_pct=0.0,
                average_win=0.0,
                average_loss=0.0,
                profit_factor=0.0,
                total_trades=0,
            )

        wins = [p.realized_pnl for p in closed_positions if p.realized_pnl > 0.0]
        losses = [p.realized_pnl for p in closed_positions if p.realized_pnl <= 0.0]

        total_win = sum(wins)
        total_loss = abs(sum(losses))

        winning_pct = len(wins) / total
        losing_pct = len(losses) / total
        average_win = total_win / len(wins) if wins else 0.0
        average_loss = total_loss / len(losses) if losses else 0.0
        profit_factor = total_win / total_loss if total_loss > 0.0 else (total_win if total_win > 0.0 else 1.0)

        return PortfolioStatistics(
            winning_pct=winning_pct,
            losing_pct=losing_pct,
            average_win=average_win,
            average_loss=average_loss,
            profit_factor=profit_factor,
            total_trades=total,
        )
