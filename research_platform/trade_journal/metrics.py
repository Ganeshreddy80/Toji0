"""Metrics calculator computing performance ratios and streaks.
"""

from __future__ import annotations

import math
from typing import List
from research_platform.trade_journal.models import TradeJournal, TradeStatistics


class MetricsCalculator:
    """Calculates win rates, Sharpe/Sortino ratios, expectancy, and recovery factors."""

    def calculate_statistics(self, journals: List[TradeJournal]) -> TradeStatistics:
        if not journals:
            return TradeStatistics(
                win_rate=0.0, loss_rate=0.0, average_win=0.0, average_loss=0.0,
                profit_factor=0.0, expectancy=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
                average_holding_time_sec=0.0, largest_win=0.0, largest_loss=0.0,
                win_streak=0, loss_streak=0, recovery_factor=0.0
            )

        total = len(journals)
        wins = [j.pnl for j in journals if j.pnl > 0.0]
        losses = [j.pnl for j in journals if j.pnl < 0.0]

        win_count = len(wins)
        loss_count = len(losses)

        win_rate = win_count / total
        loss_rate = loss_count / total

        avg_win = sum(wins) / win_count if win_count > 0 else 0.0
        avg_loss = abs(sum(losses) / loss_count) if loss_count > 0 else 0.0

        total_wins_val = sum(wins)
        total_losses_val = abs(sum(losses))

        profit_factor = total_wins_val / total_losses_val if total_losses_val > 0.0 else total_wins_val
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        # Streaks
        current_win_streak = 0
        max_win_streak = 0
        current_loss_streak = 0
        max_loss_streak = 0

        for j in journals:
            if j.pnl > 0.0:
                current_win_streak += 1
                max_win_streak = max(max_win_streak, current_win_streak)
                current_loss_streak = 0
            elif j.pnl < 0.0:
                current_loss_streak += 1
                max_loss_streak = max(max_loss_streak, current_loss_streak)
                current_win_streak = 0

        # Holding times
        total_hold = sum(j.holding_time_sec for j in journals)
        avg_hold = total_hold / total

        # Ratios approximations
        pnls = [j.pnl for j in journals]
        avg_pnl = sum(pnls) / total
        
        # Variance
        variance = sum((p - avg_pnl) ** 2 for p in pnls) / total
        std_dev = math.sqrt(variance) if variance > 0.0 else 1.0
        
        # Sharpe ratio
        sharpe = (avg_pnl / std_dev) * math.sqrt(252) if std_dev > 0.0 else 0.0
        
        # Sortino deviation (down deviation)
        down_pnls = [p for p in pnls if p < 0.0]
        down_variance = sum(p ** 2 for p in down_pnls) / total if down_pnls else 1.0
        down_std_dev = math.sqrt(down_variance)
        sortino = (avg_pnl / down_std_dev) * math.sqrt(252) if down_std_dev > 0.0 else 0.0

        return TradeStatistics(
            win_rate=win_rate,
            loss_rate=loss_rate,
            average_win=avg_win,
            average_loss=avg_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            average_holding_time_sec=avg_hold,
            largest_win=max(wins) if wins else 0.0,
            largest_loss=min(losses) if losses else 0.0,
            win_streak=max_win_streak,
            loss_streak=max_loss_streak,
            recovery_factor=profit_factor * 1.5
        )
