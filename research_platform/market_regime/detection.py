"""Unified market regime compiler and confidence scorer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from research_platform.market_regime.volatility import VolatilityDetector
from research_platform.market_regime.liquidity import LiquidityDetector
from research_platform.market_regime.trend import TrendDetector
from research_platform.market_regime.models import MarketRegime, RegimeType, VolatilityRegime, LiquidityRegime

logger = logging.getLogger(__name__)


class RegimeDetectionEngine:
    """Combines individual detectors and evaluates global regime confidence scores."""

    def __init__(self) -> None:
        self._vol_detector = VolatilityDetector()
        self._liq_detector = LiquidityDetector()
        self._trend_detector = TrendDetector()

    def detect_global_regime(
        self,
        symbol: str,
        prices: List[float],
        volumes: List[float],
        spreads: List[float],
        atr_values: List[float]
    ) -> MarketRegime:
        """Compile inputs and return a calculated MarketRegime."""
        vol = self._vol_detector.detect_volatility(prices, atr_values)
        liq = self._liq_detector.detect_liquidity(volumes, spreads)
        trend = self._trend_detector.detect_trend(prices)

        # Compute confidence score
        confidence = 0.5
        
        # Trend strength boost
        if trend in (RegimeType.BULLISH, RegimeType.BEARISH):
            confidence += 0.2
            
        # Volatility clarity boost
        if vol in (VolatilityRegime.HIGH, VolatilityRegime.LOW):
            confidence += 0.15

        # Data volume boost
        if len(prices) > 20:
            confidence += 0.15

        confidence = min(max(confidence, 0.1), 1.0)

        regime = MarketRegime(
            symbol=symbol,
            regime_type=trend,
            volatility=vol,
            liquidity=liq,
            confidence_score=confidence,
            features={
                "data_points": len(prices),
                "last_price": prices[-1] if prices else 0.0
            }
        )
        logger.info("Detected regime for %s: %s, Volatility: %s, Liquidity: %s, Confidence: %.2f",
                    symbol, trend.value, vol.value, liq.value, confidence)
        return regime
