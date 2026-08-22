"""Unit tests for MarketRegimeEngine."""

from __future__ import annotations

from price_action.analysis.market_regime_engine import MarketRegimeEngine
from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.models import (
    MarketStructureState,
    TrendMetrics,
    VolatilityMetrics,
)


def test_market_regime_squeeze():
    engine = MarketRegimeEngine()

    trend = TrendMetrics(direction=TrendDirection.SIDEWAYS)
    vol = VolatilityMetrics(is_squeeze=True, bb_bandwidth=0.03)
    struct = MarketStructureState(trend_bias=TrendDirection.SIDEWAYS)

    regime = engine.classify_regime(trend, vol, struct)
    assert regime.regime == MarketRegimeType.COMPRESSING_CONSOLIDATION
    assert regime.confidence >= 0.80


def test_market_regime_trending_bullish():
    engine = MarketRegimeEngine()

    trend = TrendMetrics(direction=TrendDirection.BULLISH, strength=0.8)
    vol = VolatilityMetrics(is_squeeze=False, bb_bandwidth=0.12)
    struct = MarketStructureState(trend_bias=TrendDirection.BULLISH)

    regime = engine.classify_regime(trend, vol, struct)
    assert regime.regime == MarketRegimeType.TRENDING_BULLISH
    assert regime.confidence >= 0.80
