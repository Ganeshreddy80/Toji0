"""Market Regime Detector evaluating trending, ranging, and volatility states.
"""

from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

class MarketRegimeDetector:
    """Classifies global market conditions dynamically into trending, ranging, or high/low volatility states."""

    def detect_regime(
        self,
        prices: List[float],
        atr_values: List[float],
        volumes: List[float]
    ) -> Dict[str, Any]:
        """Classifies the market regime using price slopes, ATR volatility ratio, and trading volume.

        Returns a dictionary:
        - regime: "TRENDING", "RANGING", "HIGH_VOLATILITY", or "LOW_VOLATILITY"
        - confidence: float (0.0 to 1.0)
        """
        if not prices:
            return {"regime": "RANGING", "confidence": 0.5}

        current_price = prices[-1]
        
        # 1. Volatility check using ATR
        current_atr = atr_values[-1] if atr_values else 0.0
        atr_ratio = (current_atr / current_price) if current_price > 0.0 else 0.0

        # 2. Trend slope using simple difference over last few periods
        slope = 0.0
        if len(prices) >= 5:
            slope = (prices[-1] - prices[-5]) / prices[-5]

        # 3. Regime classifications
        # High volatility threshold: ATR is more than 5% of price
        if atr_ratio > 0.05:
            regime = "HIGH_VOLATILITY"
            confidence = min(0.5 + (atr_ratio * 5), 1.0)
        # Strong directional slope: price shifted by more than 2.0% in 5 bars
        elif abs(slope) > 0.02:
            regime = "TRENDING"
            confidence = min(0.6 + (abs(slope) * 10), 1.0)
        # Low volatility threshold: ATR is less than 0.8% of price
        elif atr_ratio > 0.0 and atr_ratio < 0.008:
            regime = "LOW_VOLATILITY"
            confidence = 0.8
        # Otherwise ranging market
        else:
            regime = "RANGING"
            confidence = 0.75

        return {
            "regime": regime,
            "confidence": round(confidence, 2)
        }
