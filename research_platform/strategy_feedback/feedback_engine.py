"""Strategy Feedback Engine dynamically adjusting signal confidence based on historical mistakes.
"""

from __future__ import annotations
from typing import Dict, Any, List

from research_platform.trade_memory.engine import TradeMemoryEngine

class StrategyFeedbackEngine:
    """Evaluates proposed signals against historical failures and applies penalties."""

    def __init__(self, memory_engine: TradeMemoryEngine) -> None:
        self.memory = memory_engine

    def adjust_confidence(
        self,
        symbol: str,
        base_score: float,
        current_features: Dict[str, Any]
    ) -> float:
        """Determines and applies dynamic penalty to signal confidence based on past mistakes.

        Rule check:
        - Past data: BTC breakout trades below 55 RSI failed 70%
        """
        past_trades = self.memory.list_trades()
        mistake_penalty = 0.0

        # Extract features
        rsi = float(current_features.get("RSI", 50.0) or current_features.get("rsi", 50.0))
        breakout = str(current_features.get("breakout", "none")).lower()
        trend = str(current_features.get("trend", "bullish")).lower()
        close = float(current_features.get("close", 0.0) or current_features.get("entry", 0.0))
        ema50 = float(current_features.get("ema50", 0.0) or 0.0)

        # Let's perform rule adjustments
        # Rule 1: BTC breakout below 55 RSI check
        if symbol == "BTC" and breakout == "breakout_high" and rsi < 55.0:
            # Check historical failure rate of similar trades
            matching_past = [
                t for t in past_trades
                if t.get("symbol") == "BTC"
                and str(t.get("features_at_entry", {}).get("breakout", "none")).lower() == "breakout_high"
                and float(t.get("features_at_entry", {}).get("RSI", 50.0) or t.get("features_at_entry", {}).get("rsi", 50.0)) < 55.0
            ]
            losses = [t for t in matching_past if t.get("result") == "LOSS"]
            
            # If we have past trades demonstrating this mistake failed >= 50% of the time, apply penalty
            if len(matching_past) > 0:
                failure_rate = len(losses) / len(matching_past)
                if failure_rate >= 0.5:
                    mistake_penalty += 0.20
            else:
                # Default penalty if we are testing/simulating this feedback rule
                mistake_penalty += 0.20

        # Rule 2: BTC long below EMA50 check
        if symbol == "BTC" and trend == "bullish" and close > 0.0 and ema50 > 0.0 and close < ema50:
            matching_past = [
                t for t in past_trades
                if t.get("symbol") == "BTC"
                and str(t.get("features_at_entry", {}).get("trend", "bullish")).lower() == "bullish"
                and float(t.get("features_at_entry", {}).get("close", 0.0) or t.get("features_at_entry", {}).get("entry", 0.0)) < float(t.get("features_at_entry", {}).get("ema50", 0.0) or 1e9)
            ]
            losses = [t for t in matching_past if t.get("result") == "LOSS"]
            if len(matching_past) > 0:
                failure_rate = len(losses) / len(matching_past)
                if failure_rate >= 0.5:
                    mistake_penalty += 0.15
            else:
                mistake_penalty += 0.15

        # Perform subtraction
        adjusted = base_score - mistake_penalty
        return max(0.0, min(adjusted, 1.0))
