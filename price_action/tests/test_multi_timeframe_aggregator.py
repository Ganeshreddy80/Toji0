"""Unit tests for MultiTimeframeAggregator."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.multi_timeframe_aggregator import MultiTimeframeAggregator
from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.models import (
    MarketRegimeState,
    TimeframePriceActionSnapshot,
    TrendMetrics,
)


def test_multi_timeframe_aggregator_basic():
    aggregator = MultiTimeframeAggregator()
    now = datetime.now(timezone.utc)

    snap_1h = TimeframePriceActionSnapshot(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now,
        trend=TrendMetrics(direction=TrendDirection.BULLISH),
        regime=MarketRegimeState(regime=MarketRegimeType.TRENDING_BULLISH),
    )

    snap_4h = TimeframePriceActionSnapshot(
        symbol="BTC/USDT",
        timeframe="4h",
        timestamp=now,
        trend=TrendMetrics(direction=TrendDirection.BULLISH),
        regime=MarketRegimeState(regime=MarketRegimeType.TRENDING_BULLISH),
    )

    tf_dict = {"1h": snap_1h, "4h": snap_4h}
    mtf = aggregator.aggregate_snapshots("BTC/USDT", tf_dict)

    assert mtf.symbol == "BTC/USDT"
    assert mtf.primary_regime == MarketRegimeType.TRENDING_BULLISH
    assert mtf.primary_trend == TrendDirection.BULLISH
    assert mtf.confluence_score == 100.0


def test_multi_timeframe_aggregator_empty():
    aggregator = MultiTimeframeAggregator()
    mtf = aggregator.aggregate_snapshots("BTC/USDT", {})
    assert mtf.primary_regime == MarketRegimeType.RANGING
    assert mtf.confluence_score == 0.0
