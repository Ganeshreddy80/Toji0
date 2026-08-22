"""Macro Market Regime engine synthesizing trend, volatility, and market structure."""

from __future__ import annotations

import logging

from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.interfaces import IMarketRegimeEngine
from price_action.core.models import (
    MarketRegimeState,
    MarketStructureState,
    PriceActionConfig,
    TrendMetrics,
    VolatilityMetrics,
)

logger = logging.getLogger(__name__)


class MarketRegimeEngine(IMarketRegimeEngine):
    """Classifies macro market regime based on structural, trend, and volatility metrics."""

    def classify_regime(
        self,
        trend: TrendMetrics,
        volatility: VolatilityMetrics,
        market_structure: MarketStructureState,
        config: PriceActionConfig | None = None,
    ) -> MarketRegimeState:
        """Synthesize metrics into a MarketRegimeState."""
        if volatility.is_squeeze:
            return MarketRegimeState(
                regime=MarketRegimeType.COMPRESSING_CONSOLIDATION,
                confidence=0.85,
                explanation="Volatility is in a tight squeeze compression phase.",
            )

        if volatility.bb_bandwidth > 0.08 and trend.strength > 0.6:
            if trend.direction == TrendDirection.BULLISH:
                return MarketRegimeState(
                    regime=MarketRegimeType.TRENDING_BULLISH,
                    confidence=round(min(1.0, 0.6 + trend.strength * 0.4), 2),
                    explanation="Strong bullish trend with expanding volatility.",
                )
            elif trend.direction == TrendDirection.BEARISH:
                return MarketRegimeState(
                    regime=MarketRegimeType.TRENDING_BEARISH,
                    confidence=round(min(1.0, 0.6 + trend.strength * 0.4), 2),
                    explanation="Strong bearish trend with expanding volatility.",
                )

        if market_structure.trend_bias == TrendDirection.BULLISH and trend.direction == TrendDirection.BULLISH:
            return MarketRegimeState(
                regime=MarketRegimeType.TRENDING_BULLISH,
                confidence=0.80,
                explanation="Bullish market structure aligned with trend direction.",
            )
        elif market_structure.trend_bias == TrendDirection.BEARISH and trend.direction == TrendDirection.BEARISH:
            return MarketRegimeState(
                regime=MarketRegimeType.TRENDING_BEARISH,
                confidence=0.80,
                explanation="Bearish market structure aligned with trend direction.",
            )

        if volatility.bb_bandwidth > 0.10:
            return MarketRegimeState(
                regime=MarketRegimeType.VOLATILE_EXPANSION,
                confidence=0.75,
                explanation="High bandwidth expansion without clear trend alignment.",
            )

        return MarketRegimeState(
            regime=MarketRegimeType.RANGING,
            confidence=0.70,
            explanation="Consolidation in a bounded range.",
        )
