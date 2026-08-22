"""Detector for identifying execution and tactical mistakes in closed trades.
"""

from __future__ import annotations
from typing import Dict, Any, List

class MistakeDetector:
    """Evaluates entry features and execution rules to flag trade mistakes."""

    def detect_mistakes(self, trade: Dict[str, Any]) -> List[str]:
        """Detects standard trading mistakes based on market state at entry.

        Expects trade layout containing:
        - side: "BUY" or "SELL"
        - entry: float
        - stop_loss: float (optional)
        - features_at_entry: Dict with keys: RSI, trend, support, resistance, ATR, breakout, volume_change
        """
        mistakes = []
        side = trade.get("side", "BUY").upper()
        entry = float(trade.get("entry", 0.0) or trade.get("entry_price", 0.0))
        features = trade.get("features_at_entry", {}) or {}

        rsi = float(features.get("RSI", 50.0) or features.get("rsi", 50.0))
        trend = str(features.get("trend", "bullish")).lower()
        support = float(features.get("support", 0.0) or 0.0)
        resistance = float(features.get("resistance", 0.0) or 0.0)
        atr = float(features.get("ATR", 0.0) or features.get("atr", 0.0))
        breakout = str(features.get("breakout", "none")).lower()
        vol_change = float(features.get("volume_change", 0.0) or 0.0)
        stop_loss = float(trade.get("stop_loss", 0.0) or 0.0)

        # 1. Trend alignment
        if side == "BUY" and trend != "bullish":
            mistakes.append("Entered against trend")
        elif side == "SELL" and trend != "bearish":
            mistakes.append("Entered against trend")

        # 2. Support/Resistance respect
        if support > 0.0 and resistance > 0.0:
            if side == "BUY":
                near_support = entry <= (support * 1.02)
                valid_breakout = breakout == "breakout_high"
                if not (near_support or valid_breakout):
                    mistakes.append("Did not respect support/resistance")
            else:
                near_resistance = entry >= (resistance * 0.98)
                valid_breakout = breakout == "breakout_low"
                if not (near_resistance or valid_breakout):
                    mistakes.append("Did not respect support/resistance")

        # 3. RSI Confirmation
        if side == "BUY":
            if rsi >= 70.0:
                mistakes.append("RSI overbought on entry")
            elif breakout == "breakout_high" and rsi < 55.0:
                mistakes.append("Breakout trade below 55 RSI")
        else:
            if rsi <= 30.0:
                mistakes.append("RSI oversold on entry")

        # 4. Volatility/Volume
        if breakout in ("breakout_high", "breakout_low") and vol_change <= 0.0:
            mistakes.append("Low volume breakout")

        if atr > 0.0 and entry > 0.0 and (atr / entry) > 0.08:
            mistakes.append("Volatility too high")

        # 5. Stop Loss tightness
        if stop_loss > 0.0 and atr > 0.0:
            distance = abs(entry - stop_loss)
            if distance < (1.0 * atr):
                mistakes.append("Stop loss too tight")

        return mistakes
