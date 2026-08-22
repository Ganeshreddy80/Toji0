"""Generator for trading strategy candidates.
"""

from __future__ import annotations
from typing import List, Dict, Any

from research_platform.strategy_factory.models import StrategyCandidate

class StrategyGenerator:
    """Discovers and compiles combinations of indicator rules for backtesting candidate strategies."""

    def generate_candidates(self) -> List[StrategyCandidate]:
        """Generate strategy candidates representing rules configurations."""
        candidates = []

        # 1. EMA Crossover
        candidates.append(
            StrategyCandidate(
                name="EMA_CROSSOVER",
                rules={
                    "entry": {"condition1": "ema9 > ema21"},
                    "exit": {"condition1": "ema9 < ema21"},
                    "risk": {"max_loss": 0.01}
                }
            )
        )

        # 2. RSI Reversal
        candidates.append(
            StrategyCandidate(
                name="RSI_REVERSAL",
                rules={
                    "entry": {"condition1": "rsi < 30"},
                    "exit": {"condition1": "rsi > 70"},
                    "risk": {"max_loss": 0.015}
                }
            )
        )

        # 3. Breakout
        candidates.append(
            StrategyCandidate(
                name="BREAKOUT",
                rules={
                    "entry": {"condition1": "breakout == breakout_high"},
                    "exit": {"condition1": "trailing_stop"},
                    "risk": {"max_loss": 0.02}
                }
            )
        )

        # 4. Trend Following
        candidates.append(
            StrategyCandidate(
                name="TREND_FOLLOWING",
                rules={
                    "entry": {"condition1": "ema9 > ema21", "condition2": "rsi > 55"},
                    "exit": {"condition1": "rsi > 75"},
                    "risk": {"max_loss": 0.01}
                }
            )
        )

        # 5. Mean Reversion
        candidates.append(
            StrategyCandidate(
                name="MEAN_REVERSION",
                rules={
                    "entry": {"condition1": "close < support"},
                    "exit": {"condition1": "close > resistance"},
                    "risk": {"max_loss": 0.015}
                }
            )
        )

        return candidates
