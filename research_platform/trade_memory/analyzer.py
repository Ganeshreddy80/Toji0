"""Post-trade analyzer computing quality scores, detecting mistakes, and deriving lessons.
"""

from __future__ import annotations
from typing import Dict, Any

from research_platform.trade_memory.mistake_detector import MistakeDetector

class TradeAnalyzer:
    """Performs deep post-trade diagnostic analysis to extract quant lessons."""

    def __init__(self) -> None:
        self.detector = MistakeDetector()

    def analyze_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes a completed trade, flagging execution quality metrics.

        Returns a dictionary containing:
        - quality_score: int (0 to 100)
        - mistakes: List[str]
        - lesson: str
        """
        mistakes = self.detector.detect_mistakes(trade)
        quality_score = max(0, 100 - len(mistakes) * 20)

        # Generate a lesson based on mistakes detected
        if "Entered against trend" in mistakes:
            lesson = "Always verify trend alignment before entry."
        elif "Low volume breakout" in mistakes:
            lesson = "Avoid breakout trades below volume threshold."
        elif "Breakout trade below 55 RSI" in mistakes:
            lesson = "Avoid breakout trades below 55 RSI to minimize risk of false breakouts."
        elif "Stop loss too tight" in mistakes:
            lesson = "Set stop loss levels beyond 1.5x ATR to avoid premature exits."
        elif "Did not respect support/resistance" in mistakes:
            lesson = "Only trade close to S/R key levels or valid breakouts."
        elif "Volatility too high" in mistakes:
            lesson = "Reduce position size or wait for volatility contraction in highly volatile periods."
        else:
            lesson = "Trade executed with standard setup parameters and risk controls."

        return {
            "quality_score": quality_score,
            "mistakes": mistakes,
            "lesson": lesson
        }
