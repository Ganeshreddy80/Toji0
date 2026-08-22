"""AI Signal Generator producing BUY, SELL, or WAIT suggestions."""

from __future__ import annotations

import logging
from typing import Any

from research_platform.ai_signal.models import AISignalResult

logger = logging.getLogger(__name__)


class AISignalGenerator:
    """Generates execution suggestions based on confluence scoring and current ATR bounds."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def generate_signal(self, symbol: str, current_price: float) -> AISignalResult:
        # Resolve ConfluenceScoringEngine
        confluence_engine = self.container.resolve("ConfluenceScoringEngine")
        pa_orch = self.container.resolve("PriceActionOrchestrator")

        # Get confluence details
        res = confluence_engine.calculate_confluence(symbol, current_price)
        atr = pa_orch.get_atr(symbol)
        if atr <= 0.0:
            atr = current_price * 0.01  # Default to 1% of price as ATR if 0

        import os
        validation_mode = os.getenv("TOJI_VALIDATION_MODE") == "true"
        buy_threshold = 58.0 if validation_mode else 70.0
        sell_threshold = 42.0 if validation_mode else 30.0

        # Logic triggers
        if res.score >= buy_threshold:
            signal = "BUY"
            sl = current_price - (1.5 * atr)
            tp = current_price + (3.0 * atr)
            rr = 2.0
            confidence = res.score / 100.0
            expected_win_rate = 0.5 + (0.25 * confidence)
            reasoning = f"Bullish signal triggered: Confluence score is {res.score}. Explanations: " + "; ".join(res.explanations)
        elif res.score <= sell_threshold:
            signal = "SELL"
            sl = current_price + (1.5 * atr)
            tp = current_price - (3.0 * atr)
            rr = 2.0
            confidence = (100.0 - res.score) / 100.0
            expected_win_rate = 0.5 + (0.25 * confidence)
            reasoning = f"Bearish signal triggered: Confluence score is {res.score}. Explanations: " + "; ".join(res.explanations)
        else:
            signal = "WAIT"
            sl = 0.0
            tp = 0.0
            rr = 0.0
            confidence = 0.5
            expected_win_rate = 0.5
            reasoning = f"Sideways trend / weak confluence score ({res.score}). Recommending Wait."

        # Apply Strategy Feedback confidence adjustments
        try:
            from research_platform.trade_memory.engine import TradeMemoryEngine
            from research_platform.strategy_feedback.feedback_engine import StrategyFeedbackEngine
            
            if self.container.has("TradeMemoryEngine"):
                memory_engine = self.container.resolve("TradeMemoryEngine")
            else:
                memory_engine = TradeMemoryEngine()
            
            feedback_engine = StrategyFeedbackEngine(memory_engine)
            
            # Fetch latest features from feature store via Feature Platform public API (FP-2)
            if self.container.has("FeaturePlatformOrchestrator"):
                feature_platform = self.container.resolve("FeaturePlatformOrchestrator")
                latest_df = feature_platform.query_realtime([
                    "rsi", "ema9", "ema21", "ema50", "atr", "trend", "support", "resistance", "breakout", "volume_change"
                ], [symbol])
                
                if not latest_df.empty:
                    features_dict = latest_df.iloc[-1].to_dict()
                    # Normalise to uppercase feature keys
                    features_dict["RSI"] = features_dict.get("rsi", 50.0)
                    features_dict["ATR"] = features_dict.get("atr", 0.0)
                    
                    original_confidence = confidence
                    confidence = feedback_engine.adjust_confidence(symbol, confidence, features_dict)
                    expected_win_rate = 0.5 + (0.25 * confidence)
                    if confidence < original_confidence:
                        reasoning += f" [Feedback Penalty Applied: Confidence adjusted from {original_confidence:.2f} to {confidence:.2f}]"
        except Exception as e:
            logger.debug("Failed to apply strategy feedback confidence adjustment: %s", e)

        return AISignalResult(
            symbol=symbol,
            signal=signal,
            entry_price=current_price if signal != "WAIT" else 0.0,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=rr,
            confidence=confidence,
            expected_win_rate=expected_win_rate,
            reasoning=reasoning
        )
