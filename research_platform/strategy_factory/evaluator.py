"""Strategy Evaluation Engine running HistoricalReplayEngine and computing scores.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from backtesting.engine import HistoricalReplayEngine
from research_platform.strategy_factory.models import StrategyCandidate, StrategyScore

class StrategyEvaluator:
    """Evaluates strategy candidates on historical data splits, calculating key metric indicators."""

    def evaluate_strategy(
        self,
        candidate: StrategyCandidate,
        data_df: pd.DataFrame
    ) -> StrategyScore:
        """Run HistoricalReplayEngine on candidate strategy rules and compute performance score."""
        engine = HistoricalReplayEngine(data_df, strategy_name=candidate.name)
        res = engine.run_backtest()

        pnls = res.get("trade_pnls", [])
        total_trades = len(pnls)

        # 1. Calculate win rate
        wins = [p for p in pnls if p > 0.0]
        losses = [p for p in pnls if p < 0.0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        # 2. Calculate profit factor
        total_gain = sum(wins)
        total_loss = abs(sum(losses))
        profit_factor = (total_gain / total_loss) if total_loss > 0.0 else (total_gain if total_gain > 0.0 else 1.0)
        profit_factor = round(profit_factor, 2)

        # 3. Calculate max drawdown
        drawdown_pct = float(res.get("max_drawdown", 0.0))

        # 4. Sharpe Ratio
        if total_trades > 1 and np.std(pnls) > 0.0:
            mean_ret = np.mean(pnls)
            std_ret = np.std(pnls)
            sharpe = float((mean_ret / std_ret) * np.sqrt(252.0))
        else:
            # Fallback baseline
            sharpe = 1.0 if total_trades > 0 else 0.0
        sharpe = round(max(0.0, sharpe), 2)

        # 5. Average R:R
        avg_win = (np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = abs(np.mean(losses)) if len(losses) > 0 else 0.0
        avg_rr = (avg_win / avg_loss) if avg_loss > 0.0 else 1.0
        avg_rr = round(avg_rr, 2)

        # 6. Losing streak
        current_streak = 0
        max_losing_streak = 0
        for p in pnls:
            if p < 0.0:
                current_streak += 1
                if current_streak > max_losing_streak:
                    max_losing_streak = current_streak
            else:
                current_streak = 0

        # 7. Global ranking score (0-100)
        # Weights: profit factor (30%), win rate (30%), Sharpe (20%), Max drawdown (20% negative penalty)
        score_val = (win_rate * 0.3) + (min(profit_factor, 5.0) * 8.0) + (min(sharpe, 4.0) * 10.0) - (drawdown_pct * 0.5)
        score_val = max(0.0, min(score_val + 30.0, 100.0))  # normalize with baseline shift

        return StrategyScore(
            profit_factor=profit_factor,
            sharpe=sharpe,
            drawdown=drawdown_pct,
            score=round(score_val, 1)
        )
